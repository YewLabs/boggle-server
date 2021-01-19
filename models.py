from django.db import models
from spoilr.models import *

class BoggleTeamData(models.Model):
    team = models.OneToOneField(Team, on_delete=models.CASCADE)
    world = models.TextField()

    def __str__(self):
        return '%s' % (self.team)

class BoggleHighScoreData(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    level = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)

    def __str__(self):
        return '%s (%d: %d)' % (self.team, self.level, self.score)

    class Meta:
        unique_together = ('team', 'level')
