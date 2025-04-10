FROM caddy:2.7.4-builder AS builder

# Build Caddy with the security plugin
RUN xcaddy build \
  --with github.com/greenpau/caddy-security@v1.1.18

# Final stage
FROM caddy:2.7.4

# Copy the custom build
COPY --from=builder /usr/bin/caddy /usr/bin/caddy
