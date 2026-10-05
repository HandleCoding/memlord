# Optional: Postgres image with the Memlord Chinese dictionaries baked in.
# Use this instead of the bind mounts in docker-compose.yml when you want a
# single self-contained DB image (e.g. no repo checkout on the server).
#
#   docker build -t memlord-postgres-zh deploy/zhparser
#
# Private terms: put them in dicts/dict_user.txt before building, or still
# bind-mount dict_user.txt at runtime (it overrides the baked copy).
ARG BASE_IMAGE=moailaozi/postgres-images:zhparser-pgvector-17@sha256:bb9c7f67ba9c96d8eb4d75a55f80618bfdab2b04bfb2497e6e603131d2b55cba
FROM ${BASE_IMAGE}
ARG PG_MAJOR=17
COPY dicts/dict_chinese_extra.txt dicts/dict_memlord_domain.txt dicts/dict_user.txt \
     /usr/share/postgresql/${PG_MAJOR}/tsearch_data/
CMD ["postgres", "-c", "zhparser.extra_dicts=dict_chinese_extra.txt,dict_memlord_domain.txt,dict_user.txt"]
