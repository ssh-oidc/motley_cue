Name: motley-cue
Version: 0.8.8
Release: 1%{?dist}

Summary: Mapper Oidc To Local idEntitY with loCal User managEment
License: MIT
URL: https://github.com/ssh-oidc/motley_cue
Source0: motley-cue.tar.gz
# Patch0: logfiles.patch
# Patch1: otp.patch
AutoReq: no

# OpenSUSE likes to have a Group
%if 0%{?suse_version} > 0
Group: System/Libraries
%endif

# The application requires Python >= 3.10 (deps use PEP 604 "X | Y" unions that
# are evaluated at runtime). Most targets ship a new-enough default python3
# (EL10, Fedora, openSUSE Tumbleweed) and build against it. The rest default to
# an older python3, so pin a newer interpreter that the distro packages:
# python3.12 on EL8 and EL9 (defaults 3.6 / 3.9), python311 on openSUSE Leap
# 15.x (default 3.6). The Makefile picks the newest python3.x >= 3.10 present,
# so EL8 must pin 3.12 too (RHEL 8 ships it, and the probe would prefer it over
# 3.11 anyway - building with 3.12 then needs python3.12-devel for bonsai).
%if 0%{?rhel} == 8 || 0%{?centos} == 8
BuildRequires: python3.12, python3.12-devel
BuildRequires: python3-policycoreutils >= 2.9
%else
%if 0%{?rhel} == 9
BuildRequires: python3.12, python3.12-devel
%else
%if 0%{?sle_version} == 150500 || 0%{?sle_version} == 150600
BuildRequires: python311, python311-devel
BuildRequires: python311-pip, python311-setuptools
BuildRequires: python3-policycoreutils >= 3.0
%else
BuildRequires: python3, python3-devel
%if 0%{?suse_version}
BuildRequires: python3-policycoreutils >= 3.0
%endif
%endif
%endif
%endif

# Headers for bonsai (feudalAdapter's LDAP backend): it ships no wheels and is
# always compiled from source, so it needs the OpenLDAP and Cyrus SASL devel
# packages (mirrors the non-python MTEAM_CI_ADDITIONAL_PACKAGES_YUM/ZYPPER).
BuildRequires: cyrus-sasl-devel
%if 0%{?suse_version}
BuildRequires: openldap2-devel
%else
BuildRequires: openldap-devel
%endif

BuildRoot:	%{_tmppath}/%{name}
%if 0%{?rhel} == 8 || 0%{?centos} == 8
Requires: python3.12
%else
%if 0%{?rhel} == 9
Requires: python3.12
%else
%if 0%{?sle_version} == 150500 || 0%{?sle_version} == 150600
Requires: python311
%else
Requires: python3
%endif
%endif
%endif

# Runtime shared libraries the bundled venv links against. AutoReq is off, so
# they are declared explicitly: bonsai needs libldap/libsasl2, the stdlib
# _ctypes needs libffi, and the stdlib sqlite3 module needs libsqlite3.
%if 0%{?rhel} || 0%{?fedora} || 0%{?centos}
Requires: openldap
Requires: cyrus-sasl-lib
Requires: libffi
%if 0%{?rhel} == 9
# EL9's sqlite-libs was built without SQLITE_ENABLE_DESERIALIZE for a long
# time, so it lacks sqlite3_deserialize which python >= 3.11 requires
# ("undefined symbol: sqlite3_deserialize"). Confirmed broken at 3.34.1-7.el9_3
# and fixed by 3.34.1-10.el9_8, so require at least that build.
Requires: sqlite-libs >= 3.34.1-10.el9_8
%else
Requires: sqlite-libs
%endif
%endif

Requires: nginx >= 1.16.1
# Trailing '~' so prerelease builds (e.g. 0.0.2~devNNN, which RPM sorts
# *before* 0.0.2) still satisfy the dependency in the dev/prerel repos.
Requires: nginx-location-includer >= 0.0.2~

%define debug_package %{nil}
%define modname motley_cue
%define venv_dir /usr/lib/%{name}
%define installroot %{buildroot}%{venv_dir}

%define share_dir /usr/share/%{name}
%define log_dir /var/log/%{modname}
%define etc_dir /etc/%{modname}
%define run_dir /run/%{modname}
%define lib_dir /var/lib/%{modname}
%define cache_dir /var/cache/%{modname}

%description
This tool provides an OIDC-protected REST interface that allows requesting
the creation, deletion, and information of a user-account.

%prep
%setup -q
# %patch -P 0 -p1

%build

%install
make install DESTDIR=%{buildroot}
./rpm/fix-venv-paths.sh %{buildroot} %{name} %{_basedir}
./rpm/compile-semodules.sh %{installroot}%{share_dir}/selinux

mkdir -p %{buildroot}{%{etc_dir},%{log_dir},%{run_dir},%{share_dir}/selinux,%{lib_dir},%{cache_dir},/etc/nginx/conf.d,/etc/nginx/location.d,/etc/caddy/handlers,/lib/systemd/system,/usr/sbin,/etc/init.d}
cp -r %{installroot}%{etc_dir}/* %{buildroot}%{etc_dir}/
# data_files installs the assurance-tier shells without the exec bit; restore it
chmod 0755 %{buildroot}%{etc_dir}/shells/mc-message %{buildroot}%{etc_dir}/shells/mc-rbash
install %{installroot}%{share_dir}/selinux/* %{buildroot}%{share_dir}/selinux/
install %{installroot}/etc/nginx/location.d/motley_cue.nginx.conf %{buildroot}/etc/nginx/location.d/motley_cue.nginx.conf
install %{installroot}/etc/caddy/handlers/motley_cue.caddy.conf %{buildroot}/etc/caddy/handlers/motley_cue.caddy.conf
install %{installroot}/etc/systemd/system/motley-cue.service %{buildroot}/lib/systemd/system/
install %{installroot}/bin/motley-cue %{buildroot}/usr/sbin/
install %{installroot}/etc/init.d/motley-cue %{buildroot}/etc/init.d/

%files
%defattr(-,root,root,-)
%license LICENSE
%dir %{venv_dir}
%dir %{etc_dir}
%dir %{log_dir}
%dir %{run_dir}
## 0700: holds the OTP token database and the key that decrypts the Access
## Tokens in it -- see [mapper.otp] in motley_cue.conf
%attr(0700,root,root) %dir %{lib_dir}
%dir %{cache_dir}
%if 0%{?centos}
%dir %{share_dir}
%endif
%config(noreplace) %{etc_dir}/*
%{venv_dir}/*
%if 0%{?centos}
%{share_dir}/*
%else
%exclude %{share_dir}/*
%endif
%config(noreplace) /etc/nginx/location.d/motley_cue.nginx.conf
%config(noreplace) /etc/caddy/handlers/motley_cue.caddy.conf
/lib/systemd/system/motley-cue.service
/usr/sbin/motley-cue
/etc/init.d/motley-cue

%changelog

%post
%if 0%{?centos}
(
    semodule -i %{share_dir}/selinux/motley-cue-gunicorn.pp
    semodule -i %{share_dir}/selinux/motley-cue-sshd.pp
    semodule -i %{share_dir}/selinux/motley-cue-nginx.pp
    setsebool -P nis_enabled 1
) || true
%endif
systemctl enable %{name} || update-rc.d %{name} defaults || true
systemctl restart %{name} || service %{name} restart || /etc/init.d/motley-cue restart || true
systemctl restart nginx || service nginx restart || nginx -s reload || nginx || true

%preun
echo "Preun: $0 $1"
if [ $1 -eq 0 ] ; then
    echo "Removing package"
    systemctl stop %{name} || service %{name} stop || /etc/init.d/motley-cue stop || true
    systemctl disable %{name} || update-rc.d -f %{name} remove || true
fi

%postun
echo "Postun: $0 $1"
# Only run on uninstall
if [ $1 = 0 ]; then
    echo "postun uninstall"
    # remove any remaining filed (e.g. the virtualenv, caches, logs, etc)
    rm -rf %{venv_dir}
    rm -rf %{etc_dir}
    rm -rf %{log_dir}
    rm -rf %{run_dir}
    rm -rf %{lib_dir}
    rm -rf %{cache_dir}
    %if 0%{?centos}
    (
        semodule -r motley-cue-gunicorn
        semodule -r motley-cue-sshd
        semodule -r motley-cue-nginx
        setsebool -P nis_enabled 0
    ) || true
    %endif
fi
# also on upgrade, i.e. $1 == 2
systemctl restart nginx || service nginx restart || nginx -s reload || nginx || true
