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
RUN pip install mcp
 


EXPOSE 5001

RUN ln -s /usr/bin/python3.11 /usr/bin/python

ADD ./.stage/commonlibs /commonlibs
ADD ./src/k8s_mcp_client.py /k8s_mcp_client.py
ADD ./src/start.sh /start.sh

RUN chmod +x /start.sh
RUN chmod +x /k8s_mcp_client.py

CMD ["./start.sh"]

