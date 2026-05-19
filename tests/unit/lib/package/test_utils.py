import os
import shutil
import tempfile
import zipfile
from unittest import TestCase
from unittest.mock import patch

from parameterized import parameterized

from samcli.lib.package import utils
from samcli.lib.package.utils import zip_folder, make_zip


class TestPackageUtils(TestCase):
    @parameterized.expand(
        [
            # path like
            "https://s3.us-west-2.amazonaws.com/bucket-name/some/path/object.html",
            "http://s3.amazonaws.com/bucket-name/some/path/object.html",
            "https://s3.dualstack.us-west-2.amazonaws.com/bucket-name/some/path/object.html",
            "https://s3.dualstack.us-west-2.amazonaws.com.cn/bucket-name/some/path/object.html",
            # virual host
            "http://bucket-name.s3.us-west-2.amazonaws.com/some/path/object.html",
            "https://bucket-name.s3-us-west-2.amazonaws.com/some/path/object.html",
            "https://bucket-name.s3.amazonaws.com/some/path/object.html",
            "https://bucket-name.s3.amazonaws.com.cn/some/path/object.html",
            # access point
            "https://access-name-123456.s3-accesspoint.us-west-2.amazonaws.com/some/path/object.html",
            "http://access-name-899889.s3-accesspoint.us-east-1.amazonaws.com/some/path/object.html",
            "http://access-name-899889.s3-accesspoint.us-east-1.amazonaws.com.cn/some/path/object.html",
            # s3://
            "s3://bucket-name/path/to/object",
        ]
    )
    def test_is_s3_url(self, url):
        self.assertTrue(utils.is_s3_url(url))

    @parameterized.expand(
        [
            # path like
            "https://s3.$region.amazonaws.com.abc/bucket-name/some/path/object.html",  # invalid domain
            "https://s3.$region.amazonaws.com/bucket-name/some/path/object.html",  # invalid region
            "https://s3.amazonaws.com/object.html",  # no bucket
            # virual host
            "https://bucket-name.s3-us-west-2.amazonaws.com/",  # no object
            # access point
            "https://access-name.s3-accesspoint.us-west-2.amazonaws.com/some/path/object.html",  # no account id
            # s3://
            "s3://bucket-name",  # no object
            "s3:://bucket-name",  # typo
        ]
    )
    def test_is_not_s3_url(self, url):
        self.assertFalse(utils.is_s3_url(url))


    @patch("samcli.lib.package.utils.create_package_zip")
    def test_make_zip_uses_native_package_zip_when_available(self, create_package_zip_mock):
        create_package_zip_mock.return_value = "/tmp/native.zip"

        self.assertEqual(utils.make_zip("/tmp/native", "/tmp/source"), "/tmp/native.zip")

        create_package_zip_mock.assert_called_once_with("/tmp/native", "/tmp/source", False)

    @patch("samcli.lib.package.utils.create_package_zip")
    def test_make_zip_falls_back_when_native_package_zip_is_unavailable(self, create_package_zip_mock):
        create_package_zip_mock.return_value = None
        tmp_folder = tempfile.mkdtemp()
        with open(os.path.join(tmp_folder, "index.js"), "w", encoding="utf-8") as file_handle:
            file_handle.write("exports.handler = () => {};" )

        zip_file = utils.make_zip(os.path.join(tmp_folder, "artifact"), tmp_folder)
        try:
            self.assertTrue(zipfile.is_zipfile(zip_file))
        finally:
            os.remove(zip_file)
            shutil.rmtree(tmp_folder, ignore_errors=True)

    @patch("samcli.lib.package.utils.platform.system")
    @patch("samcli.lib.package.utils.create_package_zip")
    def test_make_zip_skips_native_package_zip_on_windows(self, create_package_zip_mock, system_mock):
        system_mock.return_value = "Windows"
        tmp_folder = tempfile.mkdtemp()
        with open(os.path.join(tmp_folder, "index.js"), "w", encoding="utf-8") as file_handle:
            file_handle.write("exports.handler = () => {};" )

        zip_file = utils.make_zip(os.path.join(tmp_folder, "artifact"), tmp_folder)
        try:
            self.assertTrue(zipfile.is_zipfile(zip_file))
            create_package_zip_mock.assert_not_called()
        finally:
            os.remove(zip_file)
            shutil.rmtree(tmp_folder, ignore_errors=True)

    def test_zip_folder_uses_different_path_for_same_file_in_different_run(self):
        all_zip_files = set()
        previous_md5_hash = None
        for i in range(5):
            tmp_folder = tempfile.mkdtemp()
            with zip_folder(tmp_folder, make_zip) as (zip_file, md5_hash):
                self.assertNotIn(zip_file, all_zip_files, "Each zip file should be unique!")
                all_zip_files.add(zip_file)
                if not previous_md5_hash:
                    previous_md5_hash = md5_hash
                else:
                    self.assertEqual(previous_md5_hash, md5_hash)
