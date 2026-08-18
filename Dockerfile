# A slim base image: a small, minimal version of Python 3.10, just
# enough to run the app, not a full development toolchain. This keeps
# the final image smaller and faster to build and to deploy later.
FROM python:3.10-slim

# Everything from here on happens inside a fresh, isolated filesystem
# that belongs to the container, separate from this computer's own
# files, until something is copied in explicitly below.
WORKDIR /app

# Install the Python packages this project needs before copying in the
# application code. Docker caches each step in this file. Doing the
# slow dependency install as its own early step means that later, if
# only the app code changes and requirements.txt does not, rebuilding
# the image can reuse this step instead of reinstalling everything.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now copy in the actual application: the app itself, the three
# systems it calls, and the real statute and company text files.
# corpus/ is included because System B reads those files directly off
# disk at runtime, to check that a claim's quoted text really appears
# in the real source file, word for word.
COPY app.py .
COPY src/ src/
COPY corpus/ corpus/

# Documents which port the app expects to be reached on inside the
# container. This line alone does not make the app reachable from
# outside the container, "docker run" still needs its own -p flag for
# that, this is just a label for anyone reading or building on top of
# this Dockerfile later.
EXPOSE 8501

# Lets Docker, and later a cloud platform, check whether the app
# inside the container is actually working, not just whether the
# container process happens to still be running. Streamlit exposes a
# small built in health endpoint made for exactly this purpose. Using
# Python's own urllib instead of curl avoids installing an extra tool
# into the image just for this one check.
HEALTHCHECK CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')" || exit 1

# The command that runs when the container starts. --server.address
# 0.0.0.0 is required inside a container: without it, Streamlit only
# listens for connections from inside its own container, which would
# make it unreachable from outside even with the port published.
CMD ["streamlit", "run", "app.py", "--server.port=8501", "--server.address=0.0.0.0"]
