"""Route blueprints for the OpenGlaze web app.

ALL_BLUEPRINTS is the registration order. ``static_docs`` owns the catch-all
route ``/<path:path>`` and must stay LAST so specific routes win.
"""

from webapp.routes.ai import bp as ai_bp
from webapp.routes.auth_routes import bp as auth_bp
from webapp.routes.chemistry import bp as chemistry_bp
from webapp.routes.combinations import bp as combinations_bp
from webapp.routes.demo import bp as demo_bp
from webapp.routes.experiments import bp as experiments_bp
from webapp.routes.glazes import bp as glazes_bp
from webapp.routes.health import bp as health_bp
from webapp.routes.imports import bp as imports_bp
from webapp.routes.inbox import bp as inbox_bp
from webapp.routes.materials import bp as materials_bp
from webapp.routes.recipes import bp as recipes_bp
from webapp.routes.static_docs import bp as static_docs_bp
from webapp.routes.studios import bp as studios_bp
from webapp.routes.templates_routes import bp as templates_bp
from webapp.routes.uploads import bp as uploads_bp

ALL_BLUEPRINTS = [
    health_bp,
    glazes_bp,
    recipes_bp,
    materials_bp,
    imports_bp,
    combinations_bp,
    chemistry_bp,
    experiments_bp,
    uploads_bp,
    ai_bp,
    inbox_bp,
    auth_bp,
    studios_bp,
    demo_bp,
    templates_bp,
    static_docs_bp,  # catch-all: keep last
]

__all__ = ["ALL_BLUEPRINTS"]
