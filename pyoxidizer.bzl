
def make_exe():
    dist = default_python_distribution()
    policy = dist.make_python_packaging_policy()
    
    # Configuration for standalone executable
    policy.extension_module_filter = "all"
    policy.resources_location = "in-memory"
    policy.resources_location_fallback = "filesystem-relative:lib"

    python_config = dist.make_python_interpreter_config()
    python_config.run_command = "from dslate.cli import run_app; run_app()"
    
    exe = dist.to_python_executable(
        name="dslate",
        packaging_policy=policy,
        config=python_config,
    )
    
    exe.add_python_resources(exe.pip_install(["dslate", "--find-links=dist"]))
    
    return exe

def make_embedded_resources(exe):
    return exe.to_embedded_resources()

def make_install(exe):
    files = FileManifest()
    files.add_python_resource(".", exe)
    return files



register_target("exe", make_exe)
register_target("resources", make_embedded_resources, depends=["exe"], default_build_script=True)
register_target("install", make_install, depends=["exe"], default=True)

resolve_targets()
