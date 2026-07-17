# Fresh end-user machine for testing the Cisco Advisory Impact Analyzer installer.
#
# This image is built by tools/install-test/test-install.sh with the *staged release*
# as the build context (never the repo), so no .env / .venv / inventory ever enters it.
#
# python:3.9-slim pins the MINIMUM supported Python (3.9) on Debian slim and already
# ships pip, venv, ensurepip, ca-certificates and bash. We deliberately install NOTHING
# here — the real install.py must create the .venv and pull the dependencies itself, so
# the container is a true clean slate before the maintainer runs the installer.
FROM python:3.9-slim

# A plain working directory holds the unpacked release. Nothing is preinstalled.
WORKDIR /work/app
COPY . /work/app

# Land the maintainer in an interactive shell; test-install.sh runs this with -it.
CMD ["/bin/bash"]
