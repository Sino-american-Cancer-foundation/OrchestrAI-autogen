"""
Tests for MCP utility functions
"""
import unittest
from unittest.mock import patch, MagicMock
from probill.utils._mcp_utils import check_and_create_server_params

class TestMcpUtils(unittest.TestCase):
    """Tests for the MCP utility functions"""

    @patch("probill.utils.mcp_utils.StdioServerParams")
    @patch("probill.utils.mcp_utils.SseServerParams")
    def test_check_and_create_server_params_dict_stdio(self, mock_sse_params, mock_stdio_params):
        """Test check_and_create_server_params with dict for StdioServerParams"""
        # Setup mock
        mock_stdio_params.return_value = "stdio_params_obj"
        
        # Test with dict containing command (StdioServerParams) without type field
        stdio_dict = {
            "command": ["python", "-m", "server"],
            "args": ["--debug"],
            "env": {"DEBUG": "1"},
            "read_timeout_seconds": 10.0
        }
        
        result = check_and_create_server_params(stdio_dict)
        
        # Verify StdioServerParams was created with correct args
        mock_stdio_params.assert_called_once_with(
            command=stdio_dict["command"],
            args=stdio_dict["args"],
            env=stdio_dict["env"],
            read_timeout_seconds=stdio_dict["read_timeout_seconds"]
        )
        self.assertEqual(result, "stdio_params_obj")
        
        # Reset the mock for the next test
        mock_stdio_params.reset_mock()
        
        # Test with dict containing command and type field
        stdio_dict_with_type = {
            "type": "StdioServerParams",
            "command": ["python", "-m", "server"],
            "args": ["--debug"],
            "env": {"DEBUG": "1"},
            "read_timeout_seconds": 10.0
        }
        
        result = check_and_create_server_params(stdio_dict_with_type)
        
        # Verify StdioServerParams was created with correct args
        mock_stdio_params.assert_called_once_with(
            command=stdio_dict_with_type["command"],
            args=stdio_dict_with_type["args"],
            env=stdio_dict_with_type["env"],
            read_timeout_seconds=stdio_dict_with_type["read_timeout_seconds"]
        )
        self.assertEqual(result, "stdio_params_obj")

    @patch("probill.utils.mcp_utils.StdioServerParams")
    @patch("probill.utils.mcp_utils.SseServerParams")
    def test_check_and_create_server_params_dict_sse(self, mock_sse_params, mock_stdio_params):
        """Test check_and_create_server_params with dict for SseServerParams"""
        # Setup mock
        mock_sse_params.return_value = "sse_params_obj"
        
        # Test with dict containing url (SseServerParams) without type field
        sse_dict = {
            "url": "http://localhost:8080/mcp",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30.0,
            "sse_read_timeout": 600.0
        }
        
        result = check_and_create_server_params(sse_dict)
        
        # Verify SseServerParams was created with correct args
        mock_sse_params.assert_called_once_with(
            url=sse_dict["url"],
            headers=sse_dict["headers"],
            timeout=sse_dict["timeout"],
            sse_read_timeout=sse_dict["sse_read_timeout"]
        )
        self.assertEqual(result, "sse_params_obj")
        
        # Reset the mock for the next test
        mock_sse_params.reset_mock()
        
        # Test with dict containing url and type field
        sse_dict_with_type = {
            "type": "SseServerParams",
            "url": "http://localhost:8080/mcp",
            "headers": {"Authorization": "Bearer token"},
            "timeout": 30.0,
            "sse_read_timeout": 600.0
        }
        
        result = check_and_create_server_params(sse_dict_with_type)
        
        # Verify SseServerParams was created with correct args
        mock_sse_params.assert_called_once_with(
            url=sse_dict_with_type["url"],
            headers=sse_dict_with_type["headers"],
            timeout=sse_dict_with_type["timeout"],
            sse_read_timeout=sse_dict_with_type["sse_read_timeout"]
        )
        self.assertEqual(result, "sse_params_obj")

    @patch("probill.utils.mcp_utils.StdioServerParams")
    @patch("probill.utils.mcp_utils.SseServerParams")
    def test_check_and_create_server_params_object(self, mock_sse_params, mock_stdio_params):
        """Test check_and_create_server_params with already created objects"""
        # Create mock objects
        mock_stdio_obj = MagicMock()
        mock_sse_obj = MagicMock()
        
        # Setup type checking to simulate isinstance check
        mock_stdio_obj.__class__ = MagicMock()
        mock_sse_obj.__class__ = MagicMock()
        
        # Test with existing objects - should return as is
        with patch("probill.utils.mcp_utils.isinstance", return_value=True):
            self.assertEqual(check_and_create_server_params(mock_stdio_obj), mock_stdio_obj)
            self.assertEqual(check_and_create_server_params(mock_sse_obj), mock_sse_obj)
        
    def test_check_and_create_server_params_none(self):
        """Test check_and_create_server_params with None"""
        self.assertIsNone(check_and_create_server_params(None))
        
    def test_check_and_create_server_params_invalid_dict(self):
        """Test check_and_create_server_params with invalid dict"""
        # Dict with neither command nor url
        invalid_dict = {"foo": "bar"}
        
        with self.assertRaises(ValueError):
            check_and_create_server_params(invalid_dict)
        
        # Dict with invalid type
        invalid_type_dict = {
            "type": "InvalidServerParams",
            "foo": "bar"
        }
        
        with self.assertRaises(ValueError):
            check_and_create_server_params(invalid_type_dict)
            
    def test_check_and_create_server_params_invalid_type(self):
        """Test check_and_create_server_params with invalid type"""
        with self.assertRaises(TypeError):
            check_and_create_server_params(123)  # Integer is not a valid type
            
        with self.assertRaises(TypeError):
            check_and_create_server_params("string")  # String is not a valid type
            

if __name__ == "__main__":
    unittest.main()
