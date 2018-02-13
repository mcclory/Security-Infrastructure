FROM python:3.6-alpine
MAINTAINER Patrick McClory <pmdev@introspectdata.com>

VOLUME /root/.aws

WORKDIR /usr/src/ucsd-cloud-cli

COPY . /usr/src/ucsd-cloud-cli/

RUN pip install -r /usr/src/ucsd-cloud-cli/requirements/prod.txt

ENV CLI_PROMPT=

ENTRYPOINT ["python", "-m", "ucsd_cloud_cli"]

CMD ["--help"]
