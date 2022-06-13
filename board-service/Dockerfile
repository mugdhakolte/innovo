# pull official base image
FROM python:3.6-alpine

# set environment variables
ENV PYTHONUNBUFFERED 1

# make directory to copy code
RUN mkdir /code

# set work directory
WORKDIR /code

# copy project
COPY . .

COPY .env.production .env


# install gunicorn
RUN pip install gunicorn

RUN apk add --no-cache jpeg-dev zlib-dev make
RUN apk add --no-cache libmemcached-dev zlib-dev
RUN apk add --no-cache libffi libffi-dev
RUN apk add --no-cache --virtual .build-deps build-base linux-headers  && pip install pip --upgrade 
    
# install dependencies
RUN \
 apk add --no-cache postgresql-libs && \
 apk add --no-cache --virtual .build-deps gcc musl-dev postgresql-dev

RUN \
 python3 -m pip install --no-binary :all: pynacl==1.3.0

RUN \
 python3 -m pip install -r docs/requirements.txt --no-cache-dir && \
 apk --purge del .build-deps

# collect all static files in single location 
#RUN python3 manage.py collectstatic --noinput
