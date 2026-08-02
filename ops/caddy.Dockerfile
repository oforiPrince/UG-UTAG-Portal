FROM golang:1.26.4-alpine AS builder

ARG CADDY_VERSION=v2.11.4
WORKDIR /src
RUN --mount=type=cache,target=/go/pkg/mod \
    --mount=type=cache,target=/root/.cache/go-build \
    go mod init ug-utag-caddy-build \
    && go get github.com/caddyserver/caddy/v2/cmd/caddy@${CADDY_VERSION} \
    && go get google.golang.org/grpc@v1.82.1 \
    && go build -trimpath -ldflags="-s -w" -o /out/caddy \
        github.com/caddyserver/caddy/v2/cmd/caddy

FROM alpine:3.23

RUN apk upgrade --no-cache \
    && apk add --no-cache ca-certificates libcap \
    && addgroup -S caddy \
    && adduser -S -G caddy caddy \
    && mkdir -p /config/caddy /data/caddy /etc/caddy /srv \
    && chown -R caddy:caddy /config /data /etc/caddy /srv
COPY --from=builder --chown=caddy:caddy /out/caddy /usr/bin/caddy
RUN setcap cap_net_bind_service=+ep /usr/bin/caddy

USER caddy
WORKDIR /srv
ENTRYPOINT ["caddy"]
CMD ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]
