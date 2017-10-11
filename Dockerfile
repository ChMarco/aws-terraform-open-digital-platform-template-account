FROM python:2.7.13-wheezy
ADD . /app
ENV PYTHONPATH=/app
RUN mkdir /root/.aws
RUN pip install -r /app/bin/requirements.txt

CMD python /app/bin/spec-generator.py report
# take environment vars to run scripts