FROM golang:1.24 AS build
WORKDIR /src
COPY go.mod ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux GOARCH=amd64 go build -o /out/context-api ./cmd/context-api

FROM gcr.io/distroless/base-debian12
COPY --from=build /out/context-api /context-api
EXPOSE 8080
ENTRYPOINT ["/context-api"]
