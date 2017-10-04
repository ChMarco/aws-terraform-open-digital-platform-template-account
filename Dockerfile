FROM python:2.7.13-wheezy
ADD /app /app
ENV PYTHONPATH=/bin
RUN mkdir /root/.aws
RUN pip install -r /app/requirements.txt