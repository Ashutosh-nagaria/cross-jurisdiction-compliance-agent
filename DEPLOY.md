# Deploying this app

This explains how to run the compliance agent inside a container on
your own computer, and what would still be needed to put it on the
internet for real. Nothing here deploys anything anywhere, it only
makes the app deployable.

## What a container actually is

A container is a self contained package with the app's code, the exact
version of Python it needs, and every library it depends on, all
bundled together. Right now this app only works because of everything
already set up on this one computer: a Python virtual environment,
installed packages, and so on. A container takes a snapshot of all of
that into a single image that runs the same way on any machine with
Docker installed, including a cloud server, without repeating any of
that setup by hand.

## Building the image

From the project folder, run:

    docker build -t compliance-agent .

This reads the Dockerfile, installs the Python packages listed in
requirements.txt inside a fresh, isolated environment, copies in the
app code and the statute and company text files it needs, and saves
the result as an image named compliance-agent. This step only builds
the image, it does not start the app, and it does not need any real
API keys to succeed.

## Running the container locally

The app needs the same three secret keys as before, for MongoDB,
Voyage, and Anthropic, but those must never be baked into the image
itself, since anyone who later got a copy of the image could read them
straight out of it. Instead, pass the existing .env file in at the
moment the container starts:

    docker run --env-file .env -p 8501:8501 compliance-agent

--env-file .env loads the same secrets already used locally, without
ever copying that file into the image. -p 8501:8501 connects the
container's internal port 8501 to the same port on your own computer,
so the app is reachable at http://localhost:8501, the same way it
would be if it were started directly with streamlit run.

## What a real cloud deployment would still need

This project has not been deployed anywhere, this chapter only makes it
deployable. To actually put it on the internet using a platform such as
Streamlit Community Cloud, Render, or a similar service, the next steps
would be: push this repository, or the built image, somewhere the
hosting platform can read it from, set the same three secret keys as
environment variables inside that platform's own settings screen rather
than in any file that gets uploaded, confirm the platform will run the
container on port 8501 or let it detect the port from this Dockerfile,
and decide on a real domain name and some form of access control, since
right now anyone with the link would be able to run real, billable
questions through it.
