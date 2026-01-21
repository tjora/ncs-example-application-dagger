from multiprocessing import Condition

import dagger
import yaml
from dagger import dag, function, object_type

WEST_CONFIG = """[manifest]
path = {path}
file = {file}
"""


@object_type
class NcsDaggerHack:
    @function
    async def west_unfreeze_git(
        self, repository: str, ref: str, freezefile: str
    ) -> dagger.Container:
        """
        Fetch project from git repository and dependencies from the west.freeze file

        west.freeze obtained with command hosted at git repository alongside the west.yaml manifest
            west manifest --freeze --active-only > west.freeze
        """
        # Get the contents of the file
        manifest_repo_dir = dag.git(repository).ref(ref).tree()
        west_freezefile = manifest_repo_dir.file(freezefile)
        contents = await west_freezefile.contents()

        return await self._build_checkout(
            manifest=contents, manifest_repo_dir=manifest_repo_dir
        )

    @function
    async def west_unfreeze(
        self, src: dagger.Directory, freezefile: str
    ) -> dagger.Container:
        """
        Fetch dependencies from west.freeze file in src directory

        west.freeze obtained with command hosted at git repository alongside the west.yaml manifest
            west manifest --freeze --active-only > west.freeze
        """
        # Get the contents of the file
        freezefile_f = src.file(freezefile)
        contents = await freezefile_f.contents()
        return await self._build_checkout(manifest=contents, manifest_repo_dir=src)

    def _build_checkout(self, manifest, manifest_repo_dir):
        manifest = yaml.safe_load(manifest)
        west_dir = dag.directory().with_new_file(
            "config",
            WEST_CONFIG.format(
                path=manifest["manifest"]["self"]["path"], file="west.yml"
            ),  # TODO: Add these to manifest
        )

        value = dag.container().from_("ghcr.io/nrfconnect/sdk-nrf-toolchain:latest")
        value = value.with_mounted_directory(
            "/src/" + manifest["manifest"]["self"]["path"],
            manifest_repo_dir,
        ).with_mounted_directory(
            "/src/.west",
            west_dir,
        )
        for project in manifest["manifest"]["projects"]:
            repo_dir = (
                dag.git(project["url"])
                .ref(project["revision"])
                .tree()
                .with_new_file("/.git/refs/heads/manifest-rev", project["revision"])
            )
            path = project.get("path", project["name"])

            # What is best here, use mounted or not? mounts faster, lets use that and check that it works
            value = value.with_mounted_directory("/src/" + path, repo_dir)
        return value.with_workdir("/src")

    @function
    async def west_build(self, container: dagger.Container, path: str):
        """
        Fetch dependencies from west.freeze file in src directory

        west.freeze obtained with command hosted at git repository alongside the west.yaml manifest
            west manifest --freeze --active-only > west.freeze
        """
        # Get the contents of the file
        return await container.with_exec(
            [
                "bash",
                "-c",
                f"""
            source /opt/toolchain-env.sh
            cd {path}
            west build --board nrf54l15dk/nrf54l15/cpuapp --pristine -o=-j4
            """,
            ]
        )

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
