# --------------------------------*- QWEB -*---------------------------------
#
#                               EGGZEC
#                Copyright: copyright (c) 2025 EGGZEC
#                          Contact: m.saud.zahir@gmail.com
#
# --------
#
#  Author(s)
#      Saud Zahir <m.saud.zahir@gmail.com>
#
#  Date
#      26 April 2026
#
#  Description
#      Test Module - Unit tests for QWEB using SGE example outputs
#
# --------
# ------------------------------------------------------------------------
#
#  Author(s)
#      Saud Zahir <m.saud.zahir@gmail.com>
#
#  Date
#      26 April 2026
#
#  Description
#      Test Module - Unit tests for QWEB using SGE example outputs
#
# --------------------------------------------------------------------------------

import unittest
from pathlib import Path

import xmltodict

from qweb.auth import AuthLevel, AuthService, User
from qweb.directory import DirectoryEntry, PassthroughDirectoryService
from qweb.sge import Job, Queue, SGEClient


TEST_DATA_DIR = Path(__file__).parent / "resources"


class TestJobParsing(unittest.TestCase):
    maxDiff = None

    def setUp(self) -> None:
        self.Job = Job

    def test_parse_job_from_dict(self) -> None:
        job_data = {
            "JB_job_number": "5074985",
            "JAT_prio": "0.56000",
            "JB_name": "test_job.sh",
            "JB_owner": "testuser",
            "state": "r",
            "JAT_start_time": "2017-09-01T13:58:12",
            "queue_name": "test@host1.example.com",
            "slots": "2",
        }
        job = self.Job.from_dict(job_data)
        self.assertEqual(job.job_id, 5074985)
        self.assertEqual(job.name, "test_job.sh")
        self.assertEqual(job.owner, "testuser")
        self.assertEqual(job.state, "r")
        self.assertEqual(job.priority, 0.56)
        self.assertEqual(job.slots, 2)

    def test_parse_pending_job(self) -> None:
        job_data = {
            "JB_job_number": "6176888",
            "JAT_prio": "0.00000",
            "JB_name": "phs_obs_20130201_002.sh",
            "JB_owner": "relleums",
            "state": "qw",
            "JB_submission_time": "2017-09-01T14:00:38",
            "queue_name": "",
            "slots": "1",
        }
        job = self.Job.from_dict(job_data)
        self.assertEqual(job.job_id, 6176888)
        self.assertEqual(job.state, "qw")
        self.assertEqual(job.queue, "")

    def test_parse_job_no_time(self) -> None:
        job_data = {
            "JB_job_number": "12345",
            "JAT_prio": "0.50000",
            "JB_name": "simple.sh",
            "JB_owner": "user1",
            "state": "r",
        }
        job = self.Job.from_dict(job_data)
        self.assertIsNone(job.submission_time)
        self.assertIsNone(job.start_time)


class TestQueueParsing(unittest.TestCase):
    def setUp(self) -> None:
        self.Queue = Queue

    def test_parse_queue_from_dict(self) -> None:
        queue_data = {
            "name": "test.q",
            "qtype": "BIP",
            "slots": "2/4",
            "load_avg": "0.36",
            "arch": "linux",
            "state": "",
        }
        queue = self.Queue.from_dict(queue_data)
        self.assertEqual(queue.name, "test.q")
        self.assertEqual(queue.qtype, "BIP")
        self.assertEqual(queue.used_slots, 2)
        self.assertEqual(queue.free_slots, 4)

    def test_parse_queue_empty_slots(self) -> None:
        queue_data = {"name": "empty.q", "qtype": "B", "slots": "0/1"}
        queue = self.Queue.from_dict(queue_data)
        self.assertEqual(queue.used_slots, 0)
        self.assertEqual(queue.free_slots, 1)


class TestXMLParsing(unittest.TestCase):
    maxDiff = None

    @classmethod
    def setUpClass(cls) -> None:
        cls.example_xml = TEST_DATA_DIR / "qstat_example.xml"

    def test_parse_full_xml(self) -> None:
        try:
            import xmltodict
        except ImportError:
            self.skipTest("xmltodict not installed")
        if not self.example_xml.exists():
            self.skipTest("XML test file not found")
        with open(self.example_xml, encoding="utf-8") as f:
            self.xml_content = f.read()
        data = xmltodict.parse(self.xml_content)
        queue_info = data["job_info"]["queue_info"]
        job_info = data["job_info"]["job_info"]
        self.assertIsNotNone(queue_info)
        self.assertIsNotNone(job_info)

    def test_xml_sample_constant(self) -> None:
        data = xmltodict.parse(XML_SAMPLE)
        queue_info = data["job_info"]["queue_info"]
        self.assertIsNotNone(queue_info)


class TestQStatCommand(unittest.TestCase):
    def test_qstat_output_parsing(self) -> None:
        stdout_sample = (
            "job-ID  prior   name       user         state submit/start at    "
            " queue                          slots ja-task-ID\n"
            "-----------------------------------------\n"
            "5074985 0.56000 fact_phs_m relleums     dt    08/31/2017 15:33:12"
            " fact_long@isdc-cn23.astro.unig     1\n"
            "5074992 0.56000 fact_phs_m relleums     dt    08/31/2017 15:33:45"
            " fact_long@isdc-cn23.astro.unig     1\n"
            "6174799 0.00000 exec.sh    relleums     qw    08/31/2017 15:34:54"
            "                                    1"
        )
        lines = stdout_sample.strip().split("\n")
        self.assertGreater(len(lines), 3)
        header = lines[0]
        self.assertIn("job-ID", header)
        self.assertIn("prior", header)
        self.assertIn("name", header)


class TestAuthService(unittest.TestCase):
    def test_user_creation(self) -> None:
        user = User(username="testuser", auth_level=AuthLevel.USER)
        self.assertEqual(user.username, "testuser")
        self.assertTrue(user.can_submit_jobs())
        self.assertFalse(user.can_delete_jobs("other"))

    def test_operator_permissions(self) -> None:
        user = User(username="operator", auth_level=AuthLevel.OPERATOR)
        auth = AuthService()
        auth.register_user("operator", AuthLevel.OPERATOR)
        user = auth.get_user("operator")
        self.assertIsNotNone(user)
        self.assertTrue(user.can_delete_jobs("any"))

    def test_password_hashing(self) -> None:
        auth = AuthService()
        password_hash = auth.hash_password("testpassword123")
        self.assertIn("$", password_hash)
        self.assertTrue(
            auth.verify_password("testuser", "testpassword123", password_hash)
        )

    def test_session_creation(self) -> None:
        auth = AuthService()
        user = User(username="testuser", auth_level=AuthLevel.USER)
        session = auth.create_session(user)
        self.assertIsNotNone(session.session_id)
        self.assertTrue(session.is_valid())
        retrieved = auth.get_session(session.session_id)
        self.assertIsNotNone(retrieved)


class TestDirectoryService(unittest.TestCase):
    def test_passthrough_directory(self) -> None:
        auth = AuthService()
        auth.register_user("testuser", AuthLevel.USER, email="test@example.com")
        directory = PassthroughDirectoryService(auth)
        self.assertTrue(directory.is_connected())
        user = directory.get_user("testuser")
        self.assertIsNotNone(user)
        self.assertEqual(user.username, "testuser")

    def test_directory_entry(self) -> None:
        entry = DirectoryEntry(
            username="testuser",
            uid=1000,
            gid=1000,
            home_directory="/home/testuser",
            shell="/bin/bash",
            email="test@example.com",
        )
        self.assertEqual(entry.username, "testuser")
        self.assertEqual(entry.uid, 1000)
        data = entry.to_dict()
        self.assertEqual(data["username"], "testuser")


class TestQWebIntegration(unittest.TestCase):
    def test_sge_client_initialization(self) -> None:
        client = SGEClient()
        self.assertIsNotNone(client.sge_root)
        self.assertIsNotNone(client.cell)

    def test_full_workflow_simulation(self) -> None:
        SGEClient()
        auth = AuthService()
        auth.register_user("testuser", AuthLevel.USER)
        user = auth.get_user("testuser")
        self.assertIsNotNone(user)
        self.assertTrue(user.can_submit_jobs())


XML_SAMPLE = """<?xml version='1.0'?>
<job_info  xmlns:xsd="http://gridengine.sunsource.net/source/browse/*checkout*/gridengine/source/dist/util/resources/schemas/qstat/qstat.xsd?revision=1.11">
  <queue_info>
    <job_list state="running">
      <JB_job_number>5074985</JB_job_number>
      <JAT_prio>0.56000</JAT_prio>
      <JB_name>fact_phs_muon_20150422_148.sh</JB_name>
      <JB_owner>relleums</JB_owner>
      <state>dt</state>
      <JAT_start_time>2017-09-01T13:58:12</JAT_start_time>
      <queue_name>fact_long@isdc-cn23.astro.unige.ch</queue_name>
      <slots>1</slots>
    </job_list>
    <job_list state="running">
      <JB_job_number>6176867</JB_job_number>
      <JAT_prio>0.56000</JAT_prio>
      <JB_name>phs_obs_20110101_001</JB_name>
      <JB_owner>relleums</JB_owner>
      <state>r</state>
      <JAT_start_time>2017-09-01T14:00:46</JAT_start_time>
      <queue_name>test@isdc-cn17.astro.unige.ch</queue_name>
      <slots>1</slots>
    </job_list>
  </queue_info>
  <job_info>
    <job_list state="pending">
      <JB_job_number>6176888</JB_job_number>
      <JAT_prio>0.00000</JAT_prio>
      <JB_name>phs_obs_20130201_002</JB_name>
      <JB_owner>relleums</JB_owner>
      <state>qw</state>
      <JB_submission_time>2017-09-01T14:00:38</JB_submission_time>
      <queue_name></queue_name>
      <slots>1</slots>
    </job_list>
    <job_list state="pending">
      <JB_job_number>6176889</JB_job_number>
      <JAT_prio>0.00000</JAT_prio>
      <JB_name>phs_obs_20130202_001</JB_name>
      <JB_owner>relleums</JB_owner>
      <state>qw</state>
      <JB_submission_time>2017-09-01T14:00:38</JB_submission_time>
      <queue_name></queue_name>
      <slots>1</slots>
    </job_list>
  </job_info>
</job_info>"""


if __name__ == "__main__":
    unittest.main()
