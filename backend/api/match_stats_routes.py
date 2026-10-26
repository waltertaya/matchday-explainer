from flask import Blueprint, request, jsonify
from openai import OpenAI

from rag import config

match_stats_bp = Blueprint('match_stats', __name__)