# Every movie on both cores, in the three cycle types; the final hashes must match
bash = find_program('bash')
testScripts = run_command('sh', '-c', 'ls *.test', check : true).stdout().strip().split('\n')
foreach script : testScripts
  foreach cycle : [ 'Simple', 'Rerecord', 'Full' ]
    test(script + ' (' + cycle + ')', bash,
      args : [ files('run_test.sh'), quickerSDLPoP2Tester.full_path(), SDLPoP2Tester.full_path(), script, '--cycleType', cycle ],
      env : [ 'POP2_GAME_PATH=' + get_option('gamePath') ],
      workdir : meson.current_source_dir(),
      depends : [ quickerSDLPoP2Tester, SDLPoP2Tester ],
      timeout : 600,
      suite : cycle,
    )
  endforeach
endforeach
