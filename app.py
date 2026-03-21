from random import randint
from flask import Flask, request
import logging
from pythonjsonlogger.json import JsonFormatter
#from opentelemetry.instrumentation.flask import FlaskInstrumentor


app = Flask(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.WARN, handlers=[handler])
logger = logging.getLogger(__name__)

#FlaskInstrumentor().instrument_app(app)

@app.route("/rolldice")
def roll_dice():
  player = request.args.get('player', default=None, type=str)
  result = str(roll())
  logger.warning("rolling the dice", extra={"player": player or "anonymous", "result": result})
  return result


def roll():
  return randint(1, 6)
