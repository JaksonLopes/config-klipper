# Equivalente ao servo_buzz_gear_on_down (que só existe na LinearServoSelector) para a
# ServoSelector da MMX: mexe a engrenagem enquanto o servo engata, evitando dente-com-dente.
# Instalação e contexto: trident/SESSION_NOTES.md (item 35).
import inspect
import logging
import math
import sys

_MISSING = object()


class ServoGearBuzz:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.count = config.getint('buzz_count', 3, minval=0, maxval=10)
        self.distance = config.getfloat('buzz_distance', 0.8, above=0., maxval=3.)
        self.speed = config.getfloat('buzz_speed', 25., above=0., maxval=100.)
        self.servo_speed = config.getfloat('servo_speed', 0., minval=0., maxval=1000.)
        self.servo_step = config.getfloat('servo_step', 3., above=0.5, maxval=30.)
        self.sweep_buzz_degrees = config.getfloat('sweep_buzz_degrees', 0., minval=0., maxval=180.)
        self.status = "não inicializado"
        self.buzz_total = 0
        self.sweep_total = 0
        self._in_grip = False
        self._move_ok = None
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('SERVO_GEAR_BUZZ', self.cmd_SERVO_GEAR_BUZZ,
                               desc="Mostra/ajusta a mexida da engrenagem e a velocidade do servo. "
                                    "Uso: SERVO_GEAR_BUZZ [COUNT=n] [DISTANCE=mm] [SPEED=mm/s] "
                                    "[SERVO_SPEED=graus/s, 0=máxima] [SWEEP=graus entre mexidas, 0=só no fim]")

    # --- Localização e patch da classe ---------------------------------------------------

    def _find_servo_selector_class(self):
        try:
            from .mmu.unit.selectors.mmu_servo_selector import ServoSelector
            return ServoSelector
        except Exception:
            pass
        for mod in list(sys.modules.values()):
            cls = getattr(mod, 'ServoSelector', None)
            if inspect.isclass(cls) and hasattr(cls, '_grip_release') \
                    and hasattr(cls, '_set_servo_angle'):
                return cls
        return None

    def _handle_connect(self):
        cls = self._find_servo_selector_class()
        if cls is None:
            self.status = "DESATIVADO: classe ServoSelector não encontrada nesta versão do Happy Hare"
            logging.warning("servo_gear_buzz: %s", self.status)
            return
        # Após RESTART o processo é o mesmo e a classe já pode estar com patch; só troca o dono
        cls._sgb_owner = self
        if not getattr(cls, '_sgb_patched', False):
            self._patch(cls)
            cls._sgb_patched = True
        self.status = self._status_text()
        logging.info("servo_gear_buzz: %s", self.status)

    def _status_text(self):
        slow = ("servo a %.0f°/s" % self.servo_speed) if self.servo_speed > 0 else "servo em velocidade máxima"
        sweep = (", mexe a cada %.0f° do giro" % self.sweep_buzz_degrees
                 if self.servo_speed > 0 and self.sweep_buzz_degrees > 0 else "")
        return "ativo (%d x +/-%.2fmm a %.0fmm/s; %s%s)" % (self.count, self.distance, self.speed,
                                                            slow, sweep)

    @staticmethod
    def _patch(cls):
        orig_grip = cls._grip_release
        orig_set = cls._set_servo_angle

        def _set_servo_angle(sel, angle):
            owner = getattr(cls, '_sgb_owner', None)
            if owner is not None and owner.servo_speed > 0:
                try:
                    owner._ramp(sel, angle)
                except Exception:
                    logging.exception("servo_gear_buzz: falha ao suavizar o servo (ignorado)")
            return orig_set(sel, angle)

        cls._set_servo_angle = _set_servo_angle

        def _grip_release(sel, lgate, release=False):
            owner = getattr(cls, '_sgb_owner', None)
            restore = None
            if owner is not None and not release:
                try:
                    restore = owner._arm(sel, lgate)
                except Exception:
                    logging.exception("servo_gear_buzz: falha ao preparar a mexida (ignorado)")
                    restore = None
            if owner is not None:
                owner._in_grip = not release
            try:
                return orig_grip(sel, lgate, release=release)
            finally:
                if owner is not None:
                    owner._in_grip = False
                if restore is not None:
                    restore()

        cls._grip_release = _grip_release

    # --- Servo mais lento ----------------------------------------------------------------

    def _ramp(self, sel, angle):
        """Passos intermediários curtos antes do movimento final (o original ainda faz o
        último passo, o tempo de espera e a atualização do estado). O servo só tem 'ir pro
        ângulo', então a velocidade é simulada subindo o ângulo aos poucos."""
        if angle < 0 or angle == sel.servo_angle:
            return
        mmu = getattr(sel, 'mmu', None)
        if mmu is None or getattr(mmu, '_is_running_test', False):
            return
        start = sel.servo_angle
        delta = abs(angle - start)
        if delta <= self.servo_step:
            return
        n = int(math.ceil(delta / self.servo_step))
        period = 0.02  # período do sinal PWM do servo
        step_time = max(period, math.ceil(delta / self.servo_speed / n / period) * period)
        always_active = bool(getattr(sel.p, 'servo_always_active', 0))
        # Mexe a engrenagem durante o giro (só ao engatar), a cada sweep_buzz_degrees de curso
        sweep = (self._in_grip and self.sweep_buzz_degrees > 0 and self.count > 0
                 and self._move_supported(mmu))
        enc_start = mmu.get_encoder_distance(dwell=None) if sweep else None
        traveled = 0.
        wiggles = 0
        mmu.movequeue_wait()
        for i in range(1, n):
            sel.servo.set_position(angle=start + (angle - start) * i / n,
                                   duration=None if always_active else step_time)
            mmu.movequeue_dwell(step_time)
            traveled += delta / n
            if sweep and traveled >= self.sweep_buzz_degrees:
                traveled = 0.
                if self._wiggle(sel, mmu, 1):
                    wiggles += 1
        if wiggles:
            mmu.set_encoder_distance(enc_start, dwell=None)
            self.sweep_total += wiggles

    # --- Lógica da mexida ----------------------------------------------------------------

    def _arm(self, sel, lgate):
        # Gancho de uso único no movequeue_dwell: dispara entre o comando do servo e a espera dele
        if self.count <= 0 or not isinstance(lgate, int) or lgate < 0:
            return None
        mmu = getattr(sel, 'mmu', None)
        if mmu is None or getattr(mmu, '_is_running_test', False):
            return None
        target = sel.servo_gate_angles[lgate]
        if target < 0 or target == sel.servo_angle:
            return None  # servo não vai se mover, não há engate a ajudar
        if not self._move_supported(mmu):
            return None

        real_dwell = mmu.movequeue_dwell
        prev_attr = mmu.__dict__.get('movequeue_dwell', _MISSING)
        state = {'done': False}

        def hooked_dwell(dwell):
            # Só dispara quando o servo acabou de receber o comando pro ângulo do gate
            if not state['done'] and sel.servo_angle == target:
                state['done'] = True
                self._buzz(sel, mmu)
            return real_dwell(dwell)

        mmu.movequeue_dwell = hooked_dwell

        def restore():
            if prev_attr is _MISSING:
                mmu.__dict__.pop('movequeue_dwell', None)
            else:
                mmu.movequeue_dwell = prev_attr

        return restore

    def _move_supported(self, mmu):
        if self._move_ok is None:
            try:
                params = inspect.signature(mmu.move_filament).parameters
                # Sem suppress_grip_change a mexida chamaria o grip de novo (recursão no servo)
                self._move_ok = 'suppress_grip_change' in params
            except Exception:
                self._move_ok = False
            if not self._move_ok:
                self.status = ("DESATIVADO: move_filament sem suppress_grip_change "
                               "nesta versão do Happy Hare")
                logging.warning("servo_gear_buzz: %s", self.status)
        return self._move_ok

    def _wiggle(self, sel, mmu, cycles):
        try:
            accel = getattr(getattr(sel.mmu_unit, 'p', None), 'gear_buzz_accel', 1000.)
            for _ in range(cycles):
                for dist in (self.distance, -self.distance):
                    mmu.move_filament(None, dist, speed=self.speed, accel=accel,
                                      encoder_dwell=None, speed_override=False,
                                      suppress_grip_change=True)
            return True
        except Exception:
            logging.exception("servo_gear_buzz: falha na mexida (ignorado)")
            return False

    def _buzz(self, sel, mmu):
        try:
            enc_start = mmu.get_encoder_distance(dwell=None)
            self._wiggle(sel, mmu, self.count)
            mmu.set_encoder_distance(enc_start, dwell=None)
            self.buzz_total += 1
            if hasattr(mmu, 'log_debug'):
                mmu.log_debug("servo_gear_buzz: engrenagem mexida %d x +/-%.2fmm no engate do servo"
                              % (self.count, self.distance))
        except Exception:
            logging.exception("servo_gear_buzz: falha durante a mexida (ignorado)")

    # --- Comando G-code --------------------------------------------------------------------

    def cmd_SERVO_GEAR_BUZZ(self, gcmd):
        self.count = gcmd.get_int('COUNT', self.count, minval=0, maxval=10)
        self.distance = gcmd.get_float('DISTANCE', self.distance, above=0., maxval=3.)
        self.speed = gcmd.get_float('SPEED', self.speed, above=0., maxval=100.)
        self.servo_speed = gcmd.get_float('SERVO_SPEED', self.servo_speed, minval=0., maxval=1000.)
        self.sweep_buzz_degrees = gcmd.get_float('SWEEP', self.sweep_buzz_degrees, minval=0., maxval=180.)
        if self.status.startswith("ativo"):
            self.status = self._status_text()
        gcmd.respond_info("servo_gear_buzz: %s - engates com mexida: %d, mexidas durante o giro: %d"
                          % (self.status, self.buzz_total, self.sweep_total))


def load_config(config):
    return ServoGearBuzz(config)
