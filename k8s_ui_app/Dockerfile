ARG VERSION="latest"
FROM amazonlinux:$VERSION
LABEL version="1.0"
LABEL author="bdastur@amazon.com"

RUN dnf install -y gcc \
    g++ \
    python3.11 python3.11-pip \
    vim wget less tar git sudo

#RUN ln -s /usr/bin/python3.11 /usr/bin/python
RUN ln -s /usr/bin/pip3.11 /usr/bin/pip


RUN pip install -U setuptools wheel
RUN pip install click
RUN pip install boto3
RUN pip install streamlit
RUN pip install kubernetes

EXPOSE 8501

RUN ln -s /usr/bin/python3.11 /usr/bin/python

ADD ./.stage/commonlibs /src/commonlibs
ADD ./src/ /src

RUN chmod +x ./src/start.sh

CMD ["./src/start.sh"]
#ENTRYPOINT ["streamlit", "run", "./src/app.py", "--server.port=8501", "--server.address=0.0.0.0"]


