FROM postgres:18.4-alpine AS hardened-rootfs

# Preserve the official entrypoint contract while replacing the bundled Go
# privilege-drop helper with Alpine's small C implementation.
RUN apk add --no-cache su-exec \
    && rm -f /usr/local/bin/gosu
COPY --chmod=0755 ops/gosu /usr/local/bin/gosu

# Flatten the hardened filesystem into a fresh final stage so an inherited
# SBOM cannot continue to attribute the removed gosu binary to the image.
FROM scratch

COPY --from=hardened-rootfs / /

ENV PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin \
    LANG=en_US.utf8 \
    PG_MAJOR=18 \
    PG_VERSION=18.4 \
    PGDATA=/var/lib/postgresql/18/docker

VOLUME /var/lib/postgresql
EXPOSE 5432
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["postgres"]
STOPSIGNAL SIGINT
