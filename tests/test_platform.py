import importlib.util
from pathlib import Path
import struct
import sys
import tempfile
import unittest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from prepare_zlib import object_identity
from prepare_snappy import expand_response_files

class PlatformTests(unittest.TestCase):
    def test_object_formats_and_architecture(self):
        with tempfile.TemporaryDirectory() as directory:
            p=Path(directory)/'x.o'
            def check(data,fmt,arch):
                p.write_bytes(data.ljust(64,b'\0'))
                actual=object_identity(p);self.assertEqual((actual['format'],actual['architecture']),(fmt,arch))
            for machine,arch in [(3,'x86'),(62,'x86_64'),(183,'aarch64')]:
                data=bytearray(20);data[:4]=b'\x7fELF';data[5]=1;data[18:20]=struct.pack('<H',machine);check(data,'ELF',arch)
            for machine,arch in [(0x14c,'x86'),(0x8664,'x86_64'),(0xaa64,'aarch64')]: check(struct.pack('<H',machine),'COFF',arch)
            for cpu,arch in [(0x1000007,'x86_64'),(0x100000c,'aarch64')]: check(b'\xcf\xfa\xed\xfe'+struct.pack('<I',cpu),'Mach-O',arch)
            p.write_bytes(b'bad');self.assertIsNone(object_identity(p))
    def test_response_file_is_bounded_to_build_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            cwd=Path(directory); (cwd/'opts.rsp').write_text('-I"some path" -DNAME=1')
            args,hashes=expand_response_files(['@opts.rsp','-c'],cwd)
            self.assertEqual(args,['-Isome path','-DNAME=1','-c']);self.assertIn('opts.rsp',hashes)
            with self.assertRaises(ValueError): expand_response_files(['@../other'],cwd)
