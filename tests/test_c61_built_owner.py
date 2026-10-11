import copy,hashlib,importlib.util,tempfile,unittest
from pathlib import Path

MODULE=Path(__file__).resolve().parent/'e2e/fixtures/c61_built_owner.py'
SHA='a'*40
def module():
 assert MODULE.is_file(), 'C61 built process ownership port missing'
 spec=importlib.util.spec_from_file_location('c61_built_owner',MODULE);value=importlib.util.module_from_spec(spec);spec.loader.exec_module(value);return value
class BuiltOwnerTests(unittest.TestCase):
 def setUp(self):
  self.temporary=tempfile.TemporaryDirectory();self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name).resolve()
  entry=self.root/'.output/server/index.mjs';entry.parent.mkdir(parents=True);entry.write_bytes(b'export {};')
  self.row={'pid':101,'cwd':str(self.root),'argv':['/usr/bin/node','.output/server/index.mjs'],'env':{'HOST':'127.0.0.1','PORT':'5173','C61_SOURCE_SHA':SHA},'socket_inodes':{'owned-inode'}}
 def test_owned_loopback_current_source_is_found(self):
  value=module().validate_owned_built_process(self.root,[self.row],{'owned-inode'},SHA);self.assertEqual(value['pid'],101);self.assertEqual(value['source_sha'],SHA)
 def test_external_and_wrong_port_bindings_are_rejected(self):
  for field,value in [('HOST','0.0.0.0'),('HOST','production.example'),('PORT','443')]:
   row=copy.deepcopy(self.row);row['env'][field]=value
   with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[row],{'owned-inode'},SHA)
 def test_foreign_worktree_is_rejected(self):
  row=copy.deepcopy(self.row);row['cwd']=str(self.root/'foreign')
  with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[row],{'owned-inode'},SHA)
 def test_old_source_and_extra_entrypoint_arguments_are_rejected(self):
  row=copy.deepcopy(self.row);row['env']['C61_SOURCE_SHA']='b'*40
  with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[row],{'owned-inode'},SHA)
  row=copy.deepcopy(self.row);row['argv'].append('--unrelated')
  with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[row],{'owned-inode'},SHA)
 def test_unrelated_process_and_missing_listener_are_rejected(self):
  row=copy.deepcopy(self.row);row['argv'][1]='other-server.mjs'
  with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[row],{'owned-inode'},SHA)
  with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[self.row],set(),SHA)
 def test_ambiguous_owner_is_rejected(self):
  row=copy.deepcopy(self.row);row['pid']=102
  with self.assertRaisesRegex(RuntimeError,'owned built'):module().validate_owned_built_process(self.root,[self.row,row],{'owned-inode'},SHA)
 def test_missing_built_entrypoint_cannot_pass(self):
  value=module().hash_built_output(self.root/'.output');self.assertEqual(value['files'],1);self.assertEqual(value['entrypoint_sha256'],hashlib.sha256(b'export {};').hexdigest())
  (self.root/'.output/server/index.mjs').unlink()
  with self.assertRaisesRegex(RuntimeError,'entrypoint'):module().hash_built_output(self.root/'.output')
if __name__=='__main__':unittest.main()
