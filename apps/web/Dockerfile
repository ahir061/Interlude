FROM node:22-slim
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_BASE=
ENV NEXT_PUBLIC_API_BASE=$NEXT_PUBLIC_API_BASE
ENV API_INTERNAL_URL=http://api:8000
RUN npm run build
RUN chown -R node:node /app/.next
USER node
CMD ["npx", "next", "start", "--hostname", "0.0.0.0"]
