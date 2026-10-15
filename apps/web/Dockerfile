# CaseProof web: Next.js standalone server. Talks only to the private API, with its own service identity.
FROM node:22-slim AS dependencies
WORKDIR /web
ENV NEXT_TELEMETRY_DISABLED=1
RUN chown node:node /web
COPY --chown=node:node apps/web/package.json apps/web/package-lock.json ./
USER node
RUN npm ci

FROM dependencies AS development
COPY --chown=node:node apps/web ./
RUN mkdir -p .next
ENV NODE_ENV=development PORT=3400 HOSTNAME=0.0.0.0
EXPOSE 3400
CMD ["npm", "run", "dev", "--", "--hostname", "0.0.0.0", "--port", "3400"]

FROM dependencies AS build
COPY --chown=node:node apps/web ./
RUN npm run build

FROM node:22-slim
WORKDIR /web
ENV NODE_ENV=production PORT=8080 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
COPY --from=build /web/.next/standalone ./
COPY --from=build /web/.next/static ./.next/static
COPY --from=build /web/public ./public
USER node
EXPOSE 8080
CMD ["node", "server.js"]
