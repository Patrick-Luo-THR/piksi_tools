#!/bin/bash

# Copyright (C) 2014-2018 Swift Navigation Inc.
# Contact: Swift <dev@swiftnav.com>

# This source is subject to the license found in the file 'LICENSE' which must
# be be distributed together with this source. All other rights reserved.

# THIS CODE AND INFORMATION IS PROVIDED "AS IS" WITHOUT WARRANTY OF ANY KIND,
# EITHER EXPRESSED OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND/OR FITNESS FOR A PARTICULAR PURPOSE.
#
# Script for setting up piksi_tools development environment across
# different development environments. It's not guaranteed to be
# idempotent, or have any other guarantees for that matter, but if
# you're having issues with your particular development platform,
# please let us know: we are trying to account for as many hacks as
# possible

####################################################################
## Utilities.

ROOT=$( (cd "$(dirname "$0")/.." || exit 1 >/dev/null; pwd -P) )

function color () {
    # Print with color.
    printf '\033[%sm%s\033[m\n' "$@"
}

purple='35;1'
red_bold='31;1'
message_color=$purple
error_color=$red_bold

function log_info () {
    color $message_color "$@"
}

function log_error () {
    color $error_color "$@"
}

####################################################################
## Linux dependency management and build

function piksi_splash_linux () {
    # Splash screen. Generated by http://patorjk.com/software/taag/.
    log_info "
          _/\/\/\/\/\____/\/\____/\/\____________________/\/\___
          _/\/\____/\/\__________/\/\__/\/\____/\/\/\/\_________
          _/\/\/\/\/\____/\/\____/\/\/\/\____/\/\/\/\____/\/\___
          _/\/\__________/\/\____/\/\/\/\__________/\/\__/\/\___
         _/\/\__________/\/\/\__/\/\__/\/\__/\/\/\/\____/\/\/\__

         Welcome to piksi_tools development installer!

    "
}


function install_dev_libs(){
    run_apt_install \
      build-essential \
      cmake \
      libgl1-mesa-dev \
      libgl1-mesa-glx \
      libgl1-mesa-dri \
      libglu1-mesa-dev \
      libx11-dev \
      qt4-qmake \
      qt4-default \
      qt4-dev-tools \
      x11-apps
    if ! bionic_like; then
        run_apt_install \
          python3.5-dev
    else
        run_apt_install \
          python3.6-dev
    fi
}

function bionic_like() {
    # Ubuntu 18.04 -> bionic
    # Mint 19 -> tara
    [[ $(lsb_release -c -s) == "bionic" ]] || \
        [[ $(lsb_release -c -s) == "tara" ]]
}

function linux_mint19() {
    [[ $(lsb_release -c -s) == "tara" ]]
}

function detect_virtualenv() {
    python -c 'import sys; sys.exit(0) if hasattr(sys, "real_prefix") else sys.exit(1)'
}

function validate_linux_mint19() {
    if linux_mint19 && ! detect_virtualenv; then
        log_error "On Linux Mint, the console must be installed inside a virtualenv."
        log_error "Create one by running:"
        log_error $'\t'"virtualenv -p python3.5 py3 --system-site-packages"
        log_error $'\t'"source py3/bin/activate"
        exit 1
    fi
}

function run_apt_install() {
    export DEBIAN_FRONTEND=noninteractive
    sudo -H -E apt-get install -y --force-yes $*
}

function run_pip3_install() {
    sudo python3 -m pip install --ignore-installed $*
}

function all_dependencies_debian () {
    run_apt_install \
         git \
         build-essential \
         python-setuptools \
         python-virtualenv \
         swig \
         libicu-dev \
         libqt4-scripttools \
         libffi-dev \
         libssl-dev \
         python-chaco
    if ! bionic_like; then
        run_apt_install \
            python-software-properties \
            python-vtk \
            python-pip \
            python3.5 \
            python3-pip
    else
        sudo apt-get install -y \
            software-properties-common \
            python-vtk6 \
            python3.6 \
            python3-pip
        sudo apt-get purge python-pip
        sudo python -m easy_install pip
    fi

    install_dev_libs
    validate_linux_mint19

    if command -v python3; then
        run_pip3_install --upgrade pip setuptools
        run_pip3_install -r ../requirements.txt
        run_pip3_install -r ../requirements_gui.txt
        run_pip3_install --upgrade awscli
    fi

    python_version=`python --version 2>&1`

    if command -v pip3; then
        run_pip3_install pyqt5==5.10.0
    fi
}


####################################################################
## Mac OS X dependency management and build

function piksi_splash_osx () {
    # Splash screen. Generated by http://patorjk.com/software/taag/.
    log_info "
         '7MM\"\"\"Mq.    db   '7MM                    db
           MM   'MM.          MM
           MM   ,M9  '7MM     MM  ,MP'  ,pP\"Ybd   '7MM
           MMmmdM9     MM     MM ;Y     8I    '\"    MM
           MM          MM     MM;Mm     'YMMMa.     MM
           MM          MM     MM  Mb.  L.    I8     MM
         .JMML.      .JMML. .JMML. YA.  M9mmmP'   .JMML.

         Welcome to piksi_tools development installer!

    "
}

function install_python_deps_osx () {

    log_info "Checking base OS X development tools..."
    sw_vers

    log_info "Installing Python dependencies..."

    if ! command -v conda; then

      log_info "Installing conda..."

      curl -sSL https://repo.anaconda.com/miniconda/Miniconda3-latest-MacOSX-x86_64.sh \
        -o install_miniconda.sh
      bash ./install_miniconda.sh -- -b
    fi

    conda update --yes conda

    conda install --yes \
      virtualenv \
      pytest \
      swig \
      six

    pip install --upgrade pip
    pip install --upgrade tox
    pip install --upgrade awscli

    local conda_env_name
    conda_env_name=$(echo "$ROOT" | sed -e "s@${HOME}/@@" -e 's@/@_@g')

    conda create -n "$conda_env_name" python=3.5 --yes
    {
      export PS1=''

      eval "$(conda shell.bash hook)"
      source activate "$conda_env_name"
    }

    pip install -r "$ROOT/requirements_dev.txt"
    pip install -r "$ROOT/requirements.txt"
    pip install -r "$ROOT/requirements_gui.txt"
    pip install -e "$ROOT"

    pip install PyQt5==5.10.0

    log_info ""
    log_info "To run piksi_tools from source, do the following:"
    log_info "  source activate ${conda_env_name}"
    log_info "  python piksi_tools/console/console.py"
    log_info ""
    log_info "To deactivate the conda Python environment, do the following:"
    log_info "  conda deactivate"
    log_info ""
}



####################################################################
## Entry points

function run_all_platforms () {
    if [[ "$OSTYPE" == "linux-"* ]]; then
        piksi_splash_linux
        log_info "Checking system dependencies for Linux..."
        log_info "Please enter your password for apt-get..."
        log_info "Updating..."
        sudo apt-get update
        all_dependencies_debian
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        piksi_splash_osx
        log_info "Checking system dependencies for OSX..."
        log_info ""
        install_python_deps_osx
    else
        log_error "This script does not support this platform. Please contact dev@swiftnav.com."
        exit 1
    fi
    log_info "Done!"
}

set -e -u

run_all_platforms

# vim: et:ts=4:sts=4:sw=4:ai:
