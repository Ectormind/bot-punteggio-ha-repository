ARG BUILD_FROM
FROM ${BUILD_FROM}
# ARG PIP_PACKAGES <-- Rimuoviamo questa riga
RUN apk add --no-cache python3 py3-pip && \
    pip install python-telegram-bot flask waitress  <-- Pacchetti inseriti qui
COPY Punteggiobot.py /Punteggiobot.py
CMD [ "python3", "/Punteggiobot.py" ]
