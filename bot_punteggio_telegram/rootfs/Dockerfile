ARG BUILD_FROM
FROM ${BUILD_FROM}

# Variabile d'ambiente che contiene i pacchetti da installare, definita in config.json
ARG PIP_PACKAGES

# Installazione Python e delle dipendenze necessarie
RUN apk add --no-cache python3 py3-pip && \
    pip install ${PIP_PACKAGES}

# Copia lo script nella root del container
COPY Punteggiobot.py /Punteggiobot.py

# Imposta il comando di esecuzione
CMD [ "python3", "/Punteggiobot.py" ]