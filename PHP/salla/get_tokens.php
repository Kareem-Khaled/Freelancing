<?php
	include 'refresh_token.php';

	function get_access_token() {
		try {
			$jsonData = file_get_contents('tokens.json');

			if ($jsonData === false) {
				throw new Exception('Failed to read file: tokens.json');
			}

			$data = json_decode($jsonData, true);

			if ($data === null) {
				throw new Exception('Failed to decode JSON data');
			}

			if (!isset($data['access_token'])) {
				throw new Exception('Access token not found in JSON data');
			}

			$accessToken = $data['access_token'];
			$expires = $data['expires'];
			$currentTimestamp = time();

			if ($expires <= $currentTimestamp) { // Access token has expired, refresh it

				return refresh_token();
			}

			// Access token is still valid, return it
			return $accessToken;
		} catch (Exception $e) {
			echo 'Error: ' . $e->getMessage();
			exit;
		}
	}
?>
