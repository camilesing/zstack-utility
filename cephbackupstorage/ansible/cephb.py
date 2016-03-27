#!/usr/bin/env python
# encoding: utf-8
import os
import sys
import argparse
from zstacklib import *

start_time = datetime.now()
# set default value
file_root = "files/cephb"
pip_url = "https=//pypi.python.org/simple/"
proxy = ""
sproxy = ""
yum_repo = 'false'
post_url = ""
virtualenv_version = "12.1.1"

# get parameter from shell
parser = argparse.ArgumentParser(description='Deploy ceph backup strorage to host')
parser.add_argument('-i',type=str, help="""specify inventory host file
                        default=/etc/ansible/hosts""")
parser.add_argument('--private-key',type=str,help='use this file to authenticate the connection')
parser.add_argument('-e',type=str, help='set additional variables as key=value or YAML/JSON')

args = parser.parse_args()
argument_dict = eval(args.e)

# update the variable from shell arguments
locals().update(argument_dict)
virtenv_path = "%s/virtualenv/cephb/" % zstack_root
cephb_root = "%s/cephb" % zstack_root
host_post_info = HostPostInfo()
host_post_info.host_inventory = args.i
host_post_info.host = host
host_post_info.post_url = post_url
host_post_info.private_key = args.private_key

# include zstacklib.py
(distro, distro_version) = get_remote_host_info(host_post_info)
zstacklib_args = ZstackLibArgs()
zstacklib_args.distro = distro
zstacklib_args.distro_version = distro_version
zstacklib_args.yum_repo = yum_repo
zstacklib_args.yum_server = yum_server
zstacklib_args.zstack_root = zstack_root
zstacklib_args.host_post_info = host_post_info
zstacklib = ZstackLib(zstacklib_args)

# name: judge this process is init install or upgrade
if file_dir_exist("path=" + cephb_root, host_post_info):
    init_install = False
else:
    init_install = True
    # name: create root directories
    command = 'mkdir -p %s %s' % (cephb_root, virtenv_path)
    run_remote_command(command, host_post_info)

# name: install virtualenv
virtual_env_status = check_and_install_virtual_env(virtualenv_version, trusted_host, pip_url, host_post_info)
if virtual_env_status == False:
    command = "rm -rf %s && rm -rf %s" % (virtenv_path, cephb_root)
    run_remote_command(command, host_post_info)
    sys.exit(1)
# name: make sure virtualenv has been setup
command = "[ -f %s/bin/python ] || virtualenv %s " % (virtenv_path, virtenv_path)
run_remote_command(command, host_post_info)

if distro == "RedHat" or distro == "CentOS":
    if yum_repo != 'false':
        command = "yum --disablerepo=* --enablerepo=%s --nogpgcheck install -y wget qemu-img" % yum_repo
        run_remote_command(command, host_post_info)
        if distro_version >= 7 :
            command = "rpm -q iptables-services || yum --disablerepo=* --enablerepo=%s --nogpgcheck install -y iptables-services " % yum_repo
            run_remote_command(command, host_post_info)
            command = "(which firewalld && service firewalld stop && chkconfig firewalld off) || true"
            run_remote_command(command, host_post_info)
    else:
        for pkg in ["wget","qemu-img"]:
            yum_install_package(pkg, host_post_info)
        if distro_version >= 7 :
            yum_install_package("iptables-services", host_post_info)
            command = "(which firewalld && service firewalld stop && chkconfig firewalld off) || true"
            run_remote_command(command, host_post_info)
    set_selinux("state=permissive policy=targeted", host_post_info)

elif distro == "Debian" or distro == "Ubuntu":
    for pkg in ["wget","qemu-utils"]:
        apt_install_packages(pkg, host_post_info)
else:
    print "unsupported OS!"
    sys.exit(1)

# name: copy zstacklib
copy_arg = CopyArg()
copy_arg.src="files/zstacklib/%s" % pkg_zstacklib
copy_arg.dest="%s/%s" % (cephb_root,pkg_zstacklib)
copy_zstacklib = copy(copy_arg, host_post_info)

if copy_zstacklib != "changed:False":
    agent_install_arg = AgentInstallArg(trusted_host, pip_url, virtenv_path, init_install)
    agent_install_arg.agent_name = "zstacklib"
    agent_install_arg.agent_root = cephb_root
    agent_install_arg.pkg_name = pkg_zstacklib
    agent_install_arg.virtualenv_site_packages = "yes"
    agent_install(agent_install_arg, host_post_info)

# name: copy ceph backupstorage agent
copy_arg = CopyArg()
copy_arg.src="%s/%s" % (file_root,pkg_cephbagent)
copy_arg.dest="%s/%s" % (cephb_root,pkg_cephbagent)
copy_cephb = copy(copy_arg, host_post_info)

if copy_cephb != "changed:False":
    agent_install_arg = AgentInstallArg(trusted_host, pip_url, virtenv_path, init_install)
    agent_install_arg.agent_name = "cephbackup"
    agent_install_arg.agent_root = cephb_root
    agent_install_arg.pkg_name = pkg_cephbagent
    agent_install(agent_install_arg, host_post_info)

# name: copy service file
# only support centos redhat debian and ubuntu
copy_arg = CopyArg()
copy_arg.src="%s/zstack-ceph-backupstorage" % file_root
copy_arg.dest="/etc/init.d/"
copy_arg.args="mode=755"
copy(copy_arg, host_post_info)
# name: restart cephbagent
service_status("name=zstack-ceph-backupstorage state=restarted enabled=yes", host_post_info)

host_post_info.start_time = start_time
handle_ansible_info("SUCC: Deploy cephbackup agent successful", host_post_info, "INFO")

sys.exit(0)