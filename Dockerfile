FROM astral/uv:python3.13-trixie

WORKDIR /project

ENV PDM_CHECK_UPDATE=false
ENV PDM_USE_UV=true

COPY pyproject.toml pdm.lock ./

RUN uvx pdm install

COPY backend ./backend
COPY migrations ./migrations
COPY entrypoint.sh ./entrypoint.sh

RUN chmod +x ./entrypoint.sh

ENTRYPOINT ["./entrypoint.sh"]