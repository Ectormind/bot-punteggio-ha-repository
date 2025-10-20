ARG BUILD_FROM
FROM ${BUILD_FROM}
ARG PIP_PACKAGES
RUN apk add --no-cache python3 py3-pip && \
    pip install ${PIP_PACKAGES}
COPY Punteggiobot.py /Punteggiobot.py
CMD [ "python3", "/Punteggiobot.py" ]
