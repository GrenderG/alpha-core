from game.world.managers.objects.timers.MirrorTimer import MirrorTimer
from utils.constants.MiscCodes import MirrorTimerTypes


class MirrorTimersManager(object):
    def __init__(self, owner):
        self.owner = owner
        self.timers = {}
        self.load()

    def load(self):
        self.timers[MirrorTimerTypes.BREATH] = MirrorTimer(self.owner, MirrorTimerTypes.BREATH, 1, 60, -1, 0)
        self.timers[MirrorTimerTypes.FATIGUE] = MirrorTimer(self.owner, MirrorTimerTypes.FATIGUE, 0, 0, 0, 0)
        self.timers[MirrorTimerTypes.FEIGNDEATH] = MirrorTimer(self.owner, MirrorTimerTypes.FEIGNDEATH, 0, 0, 0, 0)
        self.timers[MirrorTimerTypes.ENVIRONMENTAL] = MirrorTimer(self.owner, MirrorTimerTypes.ENVIRONMENTAL, 0, 0, 0, 0)

    def update(self, elapsed):
        # Handle breathing timer.
        self._check_breathing(elapsed)

        for timer in self.timers.values():
            timer.update(elapsed)

    def _check_breathing(self, elapsed):
        timer_active = self.owner.is_swimming() and self.owner.is_under_water()
        timer_scale = -1 if timer_active else 10

        # Set scale depending if timer is regenerating or depleting.
        self.timers[MirrorTimerTypes.BREATH].set_scale(timer_scale)
        # If timer should be active and is not, start it.
        if timer_active and not self.timers[MirrorTimerTypes.BREATH].active:
            self.timers[MirrorTimerTypes.BREATH].start(elapsed)
