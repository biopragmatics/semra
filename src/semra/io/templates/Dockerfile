FROM ubuntu:20.04

WORKDIR /sw

# Install and configure neo4j and python environment
RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl wget software-properties-common && \
    curl -fsSL https://debian.neo4j.com/neotechnology.gpg.key | apt-key add - && \
    add-apt-repository "deb https://debian.neo4j.com stable 4.4" && \
    apt-get install -y neo4j

# Install python
RUN apt-get update && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get install -y git zip unzip bzip2 gcc pkg-config python3.11 && \
    curl -sS https://bootstrap.pypa.io/get-pip.py | python3.11

RUN python3.11 -m pip install "semra[web] @ git+https://github.com/biopragmatics/semra.git"

# Add graph content
COPY concept_nodes.tsv.gz /sw/concept_nodes.tsv.gz
COPY mapping_nodes.tsv.gz /sw/mapping_nodes.tsv.gz
COPY evidence_nodes.tsv.gz /sw/evidence_nodes.tsv.gz
COPY mapping_set_nodes.tsv.gz /sw/mapping_set_nodes.tsv.gz
COPY mapping_edges.tsv.gz /sw/mapping_edges.tsv.gz
COPY edges.tsv.gz /sw/edges.tsv.gz

# Ingest graph content into neo4j
RUN sed -i 's/#dbms.default_listen_address/dbms.default_listen_address/' /etc/neo4j/neo4j.conf && \
    sed -i 's/#dbms.security.auth_enabled/dbms.security.auth_enabled/' /etc/neo4j/neo4j.conf && \
    neo4j-admin import --delimiter='TAB' --skip-duplicate-nodes=true --skip-bad-relationships=true \
        --relationships /sw/mapping_edges.tsv \
        --relationships /sw/edges.tsv \
        --nodes=concept=/sw/concept_nodes.tsv \
        --nodes=mapping=/sw/mapping_nodes.tsv \
        --nodes=mappingset=/sw/mapping_set_nodes.tsv \
        --nodes=evidence=/sw/evidence_nodes.tsv

RUN rm /sw/concept_nodes.tsv.gz
RUN rm /sw/mapping_nodes.tsv.gz
RUN rm /sw/evidence_nodes.tsv.gz
RUN rm /sw/mapping_set_nodes.tsv.gz
RUN rm /sw/edges.tsv.gz
RUN rm /sw/mapping_edges.tsv.gz

COPY startup.sh startup.sh
ENTRYPOINT ["/bin/bash", "/sw/startup.sh"]
