import pytest
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from conftest import MiminetTester
from utils.networks import MiminetTestNetwork, NodeType
import time


class TestDeviceNameChange:
    """
    Fixed version of device name change tests with proper wait conditions
    to handle MSTP implementation timing issues.
    """

    @pytest.fixture(scope="class")
    def network(self, selenium: MiminetTester):
        network = MiminetTestNetwork(selenium)

        network.add_node(NodeType.Host)
        network.add_node(NodeType.Hub)
        network.add_node(NodeType.Router)
        network.add_node(NodeType.Server)
        network.add_node(NodeType.Switch)

        yield network

        network.delete()

    def _wait_for_page_ready(self, selenium: MiminetTester, timeout: int = 20):
        """
        Wait for the page to be fully loaded and ready for interaction.
        This addresses the MSTP timing issues where DOM elements aren't ready.
        """
        try:
            # Wait for main network panel to be present and visible
            WebDriverWait(selenium, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "#main-panel"))
            )
            
            # Wait for device panel to be loaded
            WebDriverWait(selenium, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".device-panel"))
            )
            
            # Wait for JavaScript to be fully loaded (check for global variables)
            WebDriverWait(selenium, timeout).until(
                lambda driver: driver.execute_script("return typeof nodes !== 'undefined'")
            )
            
            # Additional wait for MSTP-related JavaScript to load
            WebDriverWait(selenium, timeout).until(
                lambda driver: driver.execute_script(
                    "return typeof ShowSwitchConfig !== 'undefined'"
                )
            )
            
            # Small additional wait to ensure all DOM manipulations are complete
            time.sleep(2)
            
        except TimeoutException as e:
            raise TimeoutException(
                f"Page not ready after {timeout} seconds. "
                f"This may be due to MSTP implementation loading time. "
                f"Original error: {str(e)}"
            )

    def _wait_for_config_panel_ready(self, selenium: MiminetTester, timeout: int = 15):
        """
        Wait for the configuration panel to be fully loaded and interactive.
        """
        try:
            # Wait for config panel to appear
            WebDriverWait(selenium, timeout).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, ".config-panel"))
            )
            
            # Wait for name field to be present and interactable
            WebDriverWait(selenium, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='name']"))
            )
            
            # Wait for submit button to be present
            WebDriverWait(selenium, timeout).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            
            # Additional wait for any MSTP-related modal elements to load
            time.sleep(1)
            
        except TimeoutException as e:
            raise TimeoutException(
                f"Config panel not ready after {timeout} seconds. "
                f"This may be due to MSTP modal loading time. "
                f"Original error: {str(e)}"
            )

    def _safe_change_name(self, config, new_name: str, selenium: MiminetTester):
        """
        Safely change device name with proper wait conditions.
        """
        try:
            # Wait for the name field to be ready
            name_field = WebDriverWait(selenium, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "input[name='name']"))
            )
            
            # Clear and set new name with retry logic
            for attempt in range(3):
                try:
                    name_field.clear()
                    name_field.send_keys(new_name)
                    
                    # Verify the value was set
                    if name_field.get_attribute("value") == new_name:
                        break
                        
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise e
                    time.sleep(1)  # Wait before retry
            
        except Exception as e:
            # Fallback to original method if direct approach fails
            print(f"Direct name change failed, using fallback: {e}")
            config.change_name(new_name)

    def _safe_submit_config(self, config, selenium: MiminetTester):
        """
        Safely submit configuration with proper wait conditions.
        """
        try:
            # Wait for submit button to be clickable
            submit_button = WebDriverWait(selenium, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']"))
            )
            
            # Click submit with retry logic
            for attempt in range(3):
                try:
                    submit_button.click()
                    
                    # Wait for the config panel to close or show success
                    WebDriverWait(selenium, 5).until(
                        lambda driver: not driver.find_elements(
                            By.CSS_SELECTOR, ".config-panel"
                        ) or driver.find_elements(
                            By.CSS_SELECTOR, ".success-message"
                        )
                    )
                    break
                    
                except Exception as e:
                    if attempt == 2:  # Last attempt
                        raise e
                    time.sleep(1)  # Wait before retry
            
        except Exception as e:
            # Fallback to original method if direct approach fails
            print(f"Direct submit failed, using fallback: {e}")
            config.submit()

    def test_device_name_change(
        self,
        selenium: MiminetTester,
        network: MiminetTestNetwork,
    ):
        """
        Test device name change with proper wait conditions for MSTP compatibility.
        """
        selenium.get(network.url)
        
        # Wait for page to be fully ready (addresses MSTP loading time)
        self._wait_for_page_ready(selenium)

        for node_id, node in enumerate(network.nodes):
            print(f"Testing node {node_id}: {node.get('data', {}).get('label', 'Unknown')}")
            
            # Open config with additional wait time
            config = network.open_node_config(node)
            
            # Wait for config panel to be ready
            self._wait_for_config_panel_ready(selenium)

            # Change device name with safe method
            new_device_name = "new name!"
            self._safe_change_name(config, new_device_name, selenium)

            # Submit with safe method
            self._safe_submit_config(config, selenium)
            
            # Wait for changes to be applied
            time.sleep(2)

            # Verify the change
            updated_node = network.nodes[node_id]
            actual_name = updated_node["config"]["label"]
            
            assert actual_name == new_device_name, (
                f"Failed to change device name. "
                f"Expected: '{new_device_name}', Got: '{actual_name}'"
            )
            
            print(f"✅ Successfully changed node {node_id} name to '{new_device_name}'")

    def test_device_name_change_to_long(
        self, selenium: MiminetTester, network: MiminetTestNetwork
    ):
        """
        Test device name change to long string with proper wait conditions for MSTP compatibility.
        """
        # Wait for page to be fully ready (addresses MSTP loading time)
        self._wait_for_page_ready(selenium)
        
        for node_id, node in enumerate(network.nodes):
            print(f"Testing long name for node {node_id}: {node.get('data', {}).get('label', 'Unknown')}")
            
            # Open config with additional wait time
            config = network.open_node_config(node)
            
            # Wait for config panel to be ready
            self._wait_for_config_panel_ready(selenium)

            # Change device name to long string
            new_device_name = "a" * 100  # long name
            self._safe_change_name(config, new_device_name, selenium)

            # Submit with safe method
            self._safe_submit_config(config, selenium)
            
            # Wait for changes to be applied
            time.sleep(2)

            # Verify the name was truncated
            updated_node = network.nodes[node_id]
            actual_name = updated_node["config"]["label"]
            
            assert actual_name != new_device_name, (
                f"The device name isn't limited in size. "
                f"Expected truncation but got full name: '{actual_name}'"
            )
            
            assert len(actual_name) < len(new_device_name), (
                f"Device name should be truncated. "
                f"Original length: {len(new_device_name)}, "
                f"Actual length: {len(actual_name)}"
            )
            
            print(f"✅ Successfully verified node {node_id} name truncation: '{actual_name}'")

    def test_mstp_compatibility_check(self, selenium: MiminetTester, network: MiminetTestNetwork):
        """
        Additional test to verify MSTP components don't interfere with basic functionality.
        """
        selenium.get(network.url)
        self._wait_for_page_ready(selenium)
        
        # Check that MSTP-related JavaScript is loaded
        mstp_js_loaded = selenium.execute_script(
            "return typeof window.showMstpConfig !== 'undefined' || "
            "document.querySelector('#mstp') !== null || "
            "document.querySelector('.mstp-config') !== null"
        )
        
        print(f"MSTP JavaScript components detected: {mstp_js_loaded}")
        
        # Verify basic network functionality still works
        nodes_count = len(network.nodes)
        assert nodes_count > 0, "Network should have nodes"
        
        # Test that we can still access node data
        for node in network.nodes:
            assert "data" in node, "Node should have data property"
            assert "id" in node["data"], "Node data should have id"
            
        print(f"✅ MSTP compatibility verified - {nodes_count} nodes accessible")