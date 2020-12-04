import os
from functools import wraps
from urllib.parse import urlencode, urlparse, quote_plus

from motor.motor_asyncio import AsyncIOMotorClient
from sanic import Sanic, response
from sanic.exceptions import abort, NotFound, Unauthorized
from sanic_session import Session, InMemorySessionInterface
from jinja2 import Environment, PackageLoader

import aiohttp
import config

from core.models import LogEntry
from core.utils import get_stack_variable, authrequired, User

OAUTH2_CLIENT_ID = config.OAUTH2_CLIENT_ID
OAUTH2_CLIENT_SECRET = config.OAUTH2_CLIENT_SECRET
OAUTH2_REDIRECT_URI = config.OAUTH2_REDIRECT_URI

API_BASE = "https://discordapp.com/api/"
AUTHORIZATION_BASE_URL = API_BASE + "/oauth2/authorize"
TOKEN_URL = API_BASE + "/oauth2/token"
ROLE_URL = API_BASE + "/guilds/{guild_id}/members/{user_id}"

prefix = os.getenv("URL_PREFIX", "/logs")
if prefix == "NONE":
    prefix = ""

app = Sanic(__name__)
app.using_oauth = len(config.OAUTH2_WHITELIST) != 0
app.bot_id = OAUTH2_CLIENT_ID

Session(app, interface=InMemorySessionInterface())
app.static("/static", "./static")

jinja_env = Environment(loader=PackageLoader("app", "templates"))


def render_template(name, *args, **kwargs):
    template = jinja_env.get_template(name + ".html")
    request = get_stack_variable("request")
    if request:
        if not 'session' in request.ctx.session: request.ctx.session["session"] = {} 
        kwargs["request"] = request
        kwargs["session"] = request.ctx.session["session"]
        kwargs["user"] = request.ctx.session["session"].get("user")
    kwargs.update(globals())
    return response.html(template.render(*args, **kwargs))


app.render_template = render_template


@app.listener("before_server_start")
async def init(app, loop):
    if config.mongoUser and config.mongoPass:
        mongo_uri = f"mongodb://{quote_plus(config.mongoUser)}:{quote_plus(config.mongoPass)}@{config.mongoHost}"
    else:
        mongo_uri = f"mongodb://{config.mongoHost}"
    
    app.db = AsyncIOMotorClient(mongo_uri).modmail
    app.session = aiohttp.ClientSession(loop=loop)
    if app.using_oauth:
        app.guild_id = config.GUILD_ID
        app.bot_token = config.BOT_TOKEN
        app.netloc = urlparse(OAUTH2_REDIRECT_URI).netloc

@app.middleware('request')
async def ensure_session_ctx(request):
    if not 'session' in request.ctx.session: request.ctx.session["session"] = {} 

async def fetch_token(code):
    data = {
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": OAUTH2_REDIRECT_URI,
        "client_id": OAUTH2_CLIENT_ID,
        "client_secret": OAUTH2_CLIENT_SECRET,
        "scope": "identify",
    }

    headers = {"Content-Type": "x-www-form-urlencoded"}

    async with app.session.post(TOKEN_URL, data=data) as resp:
        json = await resp.json()
        return json


async def get_user_info(token):
    headers = {"Authorization": f"Bearer {token}"}
    async with app.session.get(f"{API_BASE}/users/@me", headers=headers) as resp:
        return await resp.json()


async def get_user_roles(user_id):
    if not app.guild_id and app.bot_token: return []

    url = ROLE_URL.format(guild_id=app.guild_id, user_id=user_id)
    headers = {"Authorization": f"Bot {app.bot_token}"}
    async with app.session.get(url, headers=headers) as resp:
        user = await resp.json()
    return user.get("roles", [])


app.get_user_roles = get_user_roles


@app.exception(NotFound)
async def not_found(request, exc):
    return render_template("not_found")


@app.exception(Unauthorized)
async def not_authorized(request, exc):
    return render_template(
        "unauthorized", message="You do not have permission to view this page."
    )


@app.get("/")
async def index(request):
    return render_template("index")


@app.get("/login")
async def login(request):
    if not request.ctx.session["session"].get("from"):
        referer = request.headers.get("referer", "/")
        if referer != "/" and urlparse(referer).netloc != app.netloc:
            referer = "/"  # dont redirect to a different site
        request.ctx.session["session"]["from"] = referer

    data = {
        "scope": "identify",
        "client_id": OAUTH2_CLIENT_ID,
        "response_type": "code",
        "redirect_uri": OAUTH2_REDIRECT_URI,
    }

    return response.redirect(f"{AUTHORIZATION_BASE_URL}?{urlencode(data)}")


@app.get("/callback")
async def oauth_callback(request):
    if request.args.get("error"):
        return response.redirect("/login")

    code = request.args.get("code")
    token = await fetch_token(code)
    access_token = token.get("access_token")
    if access_token is not None:
        request.ctx.session["session"]["access_token"] = access_token
        request.ctx.session["session"]["logged_in"] = True
        request.ctx.session["session"]["user"] = User(await get_user_info(access_token))
        url = "/"
        if "from" in request.ctx.session["session"]:
            url = request.ctx.session["session"]["from"]
            del request.ctx.session["session"]["from"]
        return response.redirect(url)
    return response.redirect("/login")


@app.get("/logout")
async def logout(request):
    request.ctx.session["session"].clear()
    return response.redirect("/")


@app.get(prefix + "/raw/<key>")
@authrequired()
async def get_raw_logs_file(request, document):
    """Returns the plain text rendered log entry"""

    if document is None:
        abort(404)

    log_entry = LogEntry(app, document)

    return log_entry.render_plain_text()


@app.get(prefix + "/<key>")
@authrequired()
async def get_logs_file(request, document):
    """Returns the html rendered log entry"""

    if document is None:
        abort(404)

    log_entry = LogEntry(app, document)

    return log_entry.render_html()


if __name__ == "__main__":
    app.run(
        # You can change these using environment variables
        host=os.getenv("HOST", "127.0.0.1"),
        port=os.getenv("PORT", 8880),
        debug=bool(os.getenv("DEBUG", False)),
    )
