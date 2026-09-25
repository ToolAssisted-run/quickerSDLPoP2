project('quickerSDLPoP2', 'c', 'cpp',
  version : '1.0.0',
  license : 'GPL-3.0-or-later',
  default_options : [ 'cpp_std=c++20', 'c_std=gnu11', 'buildtype=release' ],
  subproject_dir : 'extern'
)

# The core: one header (source/quickerSDLPoP2/quickerSDLPoP2.hpp) plus its JaffarPlus-facing instance
subdir('source')

# Do not build any targets if this is a subproject
if meson.is_subproject() == false

  commonCompileArgs = [ '-Wfatal-errors', '-Wall' ]

  jaffarCommonSubproject = subproject('jaffarCommon')
  jaffarCommonDependency = jaffarCommonSubproject.get_variable('jaffarCommonDependency')

  # The oracle: SDLPoP2's own core, from the SDLPoP2 submodule
  sdlpop2Subproject = subproject('SDLPoP2')
  sdlpop2Dependency = sdlpop2Subproject.get_variable('sdlpop2Dependency')

  # Tester programs: the same source, once per core
  quickerSDLPoP2Tester = executable('quickerSDLPoP2Tester',
    'source/tester.cpp',
    cpp_args : [ commonCompileArgs, '-DINSTANCE_HEADER="quickerSDLPoP2/quickerInstance.hpp"' ],
    dependencies : [ jaffarCommonDependency, quickerSDLPoP2Dependency ],
  )

  SDLPoP2Tester = executable('SDLPoP2Tester',
    'source/tester.cpp',
    cpp_args : [ commonCompileArgs, '-DINSTANCE_HEADER="oracle/oracleInstance.hpp"' ],
    dependencies : [ jaffarCommonDependency, sdlpop2Dependency, oracleDependency ],
  )

  # The movie tests (they need the game's files: -DgamePath=...)
  if get_option('gamePath') != ''
    subdir('tests')
  endif

endif
