"""
This module takes care of starting the API Server, Loading the DB and Adding the endpoints
"""
from src.api.api_blueprint import api
from flask_cors import CORS

CORS(api)

from src.api.endpoints import categories as _categories
from src.api.endpoints import teams as _teams
from src.api.endpoints import trainings as _trainings
from src.api.endpoints import attendance as _attendance
from src.api.endpoints import onboarding as _onboarding
from src.api.endpoints import admin as _admin
from src.api.endpoints import club as _club
from src.api.endpoints import auth as _auth
from src.api.endpoints import receipts as _receipts
from src.api.endpoints import players as _players
from src.api.endpoints import player_performance as _player_performance
from src.api.endpoints import payments as _payments
from src.api.endpoints import tournaments as _tournaments
from src.api.endpoints import matches as _matches
from src.api.endpoints import seasons as _seasons
