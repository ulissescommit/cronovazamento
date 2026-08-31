from fastapi import Request
from fastapi.responses import RedirectResponse


def redirecionar(request: Request, caminho: str, status_code: int = 303) -> RedirectResponse:
    """Redireciona respeitando o prefixo de caminho quando a aplicação está
    atrás de um proxy reverso montado num sub-caminho (Caddy manda
    X-Forwarded-Prefix nesse caso) — sem isso, um redirect absoluto tipo
    "/amostras" escaparia do prefixo e cairia fora da aplicação."""
    prefixo = request.headers.get("x-forwarded-prefix", "")
    return RedirectResponse(f"{prefixo}{caminho}", status_code=status_code)
