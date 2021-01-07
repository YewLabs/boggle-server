from django.db import models
from spoilr.models import *

class BoggleTeamData(models.Model):
    team = models.OneToOneField(Team, on_delete=models.CASCADE)
    world = models.TextField()

class BoggleHighScoreData(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE)
    level = models.PositiveIntegerField(default=0)
    score = models.PositiveIntegerField(default=0)
