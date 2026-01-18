from dataclasses import dataclass

import dagger
from dagger import dag, function, object_type

WEST_CONFIG = """[manifest]
path = {path}
file = {file}
"""


@dataclass
class Repo:
    name: str
    path: str
    revision: str
    sha: str
    url: str


def parse(content: str):
    """
    west list --format "{name} {path} {revision} {sha} {url}" > west.lockdump
    """
    repos = []
    manifest = None
    for line in content.splitlines():
        name, path, revision, sha, url = line.split()
        if name == "manifest":
            manifest = Repo(name, path, revision, sha, url)
        else:
            repos.append(Repo(name, path, revision, sha, url))
    return repos, manifest


@object_type
class NcsDaggerHack:
    @function
    async def ncs_checkout_git(self, repository: str, ref: str, lockfile_path: str):
        """

        lockfile obtained with command hosted at git repository alongside the west.yaml manifest
            west list --format "{name} {path} {revision} {sha} {url}" > west.lockdump
        A more permanent lockfile with versioning etc must be made before making this public
        """
        # Get the contents of the file
        manifest_repo_dir = dag.git(repository).ref(ref).tree()
        west_lockfile = manifest_repo_dir.file(lockfile_path)
        contents = await west_lockfile.contents()
        repos, manifest_repo = parse(contents)
        west_dir = dag.directory().with_new_file(
            "config",
            WEST_CONFIG.format(
                path=manifest_repo.path, file="west.yml"
            ),  # TODO: Add these to manifest
        )

        value = dag.container().from_("ghcr.io/nrfconnect/sdk-nrf-toolchain:latest")
        value = value.with_mounted_directory(
            "/src/" + manifest_repo.path,
            manifest_repo_dir,
        ).with_mounted_directory(
            "/src/.west",
            west_dir,
        )
        for repo in repos:
            repo_dir = (
                dag.git(repo.url)
                .ref(repo.sha)
                .tree()
                .with_new_file("/.git/refs/heads/manifest-rev", repo.sha)
            )
            # What is best here, use mounted or not? mounts faster, lets use that and check that it works
            value = value.with_mounted_directory("/src/" + repo.path, repo_dir)

        return await value.with_workdir("/src")  # .terminal()
        # .with_exec(
        #    [
        #        "bash",
        #        "-c",
        #        """
        #    source /opt/toolchain-env.sh        #    west init -l nrf
        #    west update
        #    """,
        #    ]
        # )


# ACCEPT_JLINK_LICENSE=0 /bin/bash
# source /opt/toolchain-env.sh
# west init -l nrf
# west update
# cd nrf/samples/bluetooth/peripheral_lbs/

# west build --board nrf54l15dk/nrf54l15/cpuapp --pristine -o=-j4
