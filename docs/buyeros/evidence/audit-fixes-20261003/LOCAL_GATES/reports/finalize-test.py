from pathlib import Path
p=Path('tests/e2e-fixture-cleanup.test.mjs')
s=p.read_text(encoding='utf-8')
s=s.replace("test('every disposable-API Playwright configuration actually removes its owned container and marker',async t=>{\n  for", "test('every disposable-API Playwright configuration actually removes its owned container and marker',async t=>{\n  let checked=0;\n  for")
s=s.replace("      }finally{removeOwned(container);removeTemporary(cwd);}\n    });\n  }\n});", "      }finally{try{removeOwned(container);}finally{removeTemporary(cwd);}}\n    });\n    checked++;\n  }\n  assert.ok(checked>0,'no disposable-API configuration was verified');\n});")
s=s.replace("}finally{removeOwned(container);removeTemporary(cwd);}","}finally{try{removeOwned(container);}finally{removeTemporary(cwd);}}")
p.write_text(s,encoding='utf-8')
