from random import randint
from flask import Flask, request
import logging
#from opentelemetry.instrumentation.flask import FlaskInstrumentor


app = Flask(__name__)
logging.basicConfig(level=logging.WARN)
logger = logging.getLogger(__name__)

#FlaskInstrumentor().instrument_app(app)

@app.route("/rolldice")
def roll_dice():
  player = request.args.get('player', default=None, type=str)
  result = str(roll())
  if player:
    logger.warning("%s is rolling the dice: %s", player, result)
  else:
    logger.warning("Anonymous player is rolling the dice: %s", result)
  return result


def roll():
  return randint(1, 6)
