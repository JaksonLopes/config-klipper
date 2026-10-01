# Equivalente ao servo_buzz_gear_on_down (que só existe na LinearServoSelector) para a
# ServoSelector da MMX: mexe a engrenagem enquanto o servo engata, evitando dente-com-dente.
# Instalação e contexto: trident/SESSION_NOTES.md (item 35).
import inspect
import logging
import sys

_MISSING = object()


class ServoGearBuzz:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.count = config.getint('buzz_count', 3, minval=0, maxval=10)
        self.distance = config.getfloat('buzz_distance', 0.8, above=0., maxval=3.)
        self.speed = config.getfloat('buzz_speed', 25., above=0., maxval=100.)
        self.status = "não inicializado"
        self.buzz_total = 0
        self._move_ok = None
        self.printer.register_event_handler("klippy:connect", self._handle_connect)
        gcode = self.printer.lookup_object('gcode')
        gcode.register_command('SERVO_GEAR_BUZZ', self.cmd_SERVO_GEAR_BUZZ,
                               desc="Mostra/ajusta a mexida da engrenagem no engate do servo. "
                                    "Uso: SERVO_GEAR_BUZZ [COUNT=n] [DISTANCE=mm] [SPEED=mm/s]")

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
        self.status = "ativo (%d x +/-%.2fmm a %.0fmm/s)" % (self.count, self.distance, self.speed)
        logging.info("servo_gear_buzz: %s", self.status)

    @staticmethod
    def _patch(cls):
        orig_grip = cls._grip_release

        def _grip_release(sel, lgate, release=False):
            owner = getattr(cls, '_sgb_owner', None)
            restore = None
            if owner is not None and not release:
                try:
                    restore = owner._arm(sel, lgate)
                except Exception:
                    logging.exception("servo_gear_buzz: falha ao preparar a mexida (ignorado)")
                    restore = None
            try:
                return orig_grip(sel, lgate, release=release)
            finally:
                if restore is not None:
                    restore()

        cls._grip_release = _grip_release

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

    def _buzz(self, sel, mmu):
        try:
            accel = getattr(getattr(sel.mmu_unit, 'p', None), 'gear_buzz_accel', 1000.)
            enc_start = mmu.get_encoder_distance(dwell=None)
            for _ in range(self.count):
                for dist in (self.distance, -self.distance):
                    mmu.move_filament(None, dist, speed=self.speed, accel=accel,
                                      encoder_dwell=None, speed_override=False,
                                      suppress_grip_change=True)
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
        if self.status.startswith("ativo"):
            self.status = "ativo (%d x +/-%.2fmm a %.0fmm/s)" % (self.count, self.distance, self.speed)
        gcmd.respond_info("servo_gear_buzz: %s - engates com mexida desde o restart: %d"
                          % (self.status, self.buzz_total))


def load_config(config):
    return ServoGearBuzz(config)
