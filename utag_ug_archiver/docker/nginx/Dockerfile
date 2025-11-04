FROM nginx:1.27-alpine

RUN apk add --no-cache gettext openssl

COPY docker/nginx/entrypoint.sh /entrypoint.sh
COPY docker/nginx/default.conf.template /etc/nginx/templates/default.conf.template

RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
CMD ["nginx", "-g", "daemon off;"]
