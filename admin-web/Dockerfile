# ==============================================================================
# MediConnect - Production React Admin Web Container
# Multi-stage build: Node 20 builder -> Lightweight Nginx Alpine server
# Security: Read-only static assets, non-root Nginx execution, security headers
# ==============================================================================

# Stage 1: Build static distribution bundle
FROM node:20-alpine AS builder

WORKDIR /app

# Copy dependency specifications first for layer caching
COPY package.json package-lock.json ./

# Install clean production and development dependencies for compilation
RUN npm ci

# Copy application source code and assets
COPY . .

# Compile TypeScript and Vite production bundle
RUN npm run build

# Stage 2: Serve static bundle via hardened Nginx
FROM nginx:1.27-alpine AS runtime

# Remove default Nginx welcome page
RUN rm -rf /usr/share/nginx/html/*

# Copy hardened Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Copy compiled static assets from builder stage
COPY --from=builder /app/dist /usr/share/nginx/html

# Expose HTTP service port
EXPOSE 80

# Healthcheck probing the application entrypoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD wget --no-verbose --tries=1 --spider http://localhost/ || exit 1

# Start Nginx in foreground
CMD ["nginx", "-g", "daemon off;"]
