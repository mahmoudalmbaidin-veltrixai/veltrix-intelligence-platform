FROM postgres:17-alpine@sha256:742f40ea20b9ff2ff31db5458d127452988a2164df9e17441e191f3b72252193

# The upstream image's bundled gosu binary is built with a vulnerable Go
# standard library. Replace only that privilege-drop helper with Alpine's
# small, native su-exec equivalent; the official entrypoint invocation is
# compatible with both tools.
RUN apk add --no-cache su-exec=0.3-r0 \
    && rm /usr/local/bin/gosu \
    && ln -s /sbin/su-exec /usr/local/bin/gosu
