<?php
	function refresh_token() {

		$jsonData = file_get_contents('tokens.json');
		$data = json_decode($jsonData, true);

		$url = 'https://accounts.salla.sa/oauth2/token';

		// Data to be sent in the request body
		$data = array(
		'client_id' => '248dfd9a-53a4-4a4a-a5e2-7a7990b27e09',
		'client_secret' => '48f1d4767c17b5b6e4277740f6d6b12d',
		'grant_type' => 'refresh_token',
		'refresh_token' => $data['refresh_token'],
		'redirect_uri' => 'https://xbonendo.online/'
		);

		// Build the query string
		$queryString = http_build_query($data);

		// Initialize cURL
		$ch = curl_init();

		// Set the cURL options
		curl_setopt($ch, CURLOPT_URL, $url);
		curl_setopt($ch, CURLOPT_POST, true);
		curl_setopt($ch, CURLOPT_POSTFIELDS, $queryString);
		curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);
		curl_setopt($ch, CURLOPT_HTTPHEADER, array(
			'Content-Type: application/x-www-form-urlencoded'
		));

		// Execute the request
		$response = curl_exec($ch);

		// Check for errors
		if(curl_errno($ch)){
			$error_message = curl_error($ch);
			file_put_contents('/var/www/html/refresh.log', $error_message . PHP_EOL, FILE_APPEND);
			curl_close($ch);
			echo "Unkown Error!". PHP_EOL;
			return null;
		}

		else{
			curl_close($ch);

			// Decode the JSON response
			$responseData = json_decode($response, true);

			if (isset($responseData['error'])) {
				echo $response . PHP_EOL;
				return null;
			}
			else{

				// Extract the required fields
				$accessToken = $responseData['access_token'];
				$refreshToken = $responseData['refresh_token'];
				$expires = time() + $responseData['expires_in'];

				// Create the new JSON object
				$json = json_encode(array(
					'access_token' => $accessToken,
					'refresh_token' => $refreshToken,
					'expires' => $expires
				));

				// Log the new response
				file_put_contents('/var/www/html/tokens.json', $json);

				echo "Refreshed Successfully!". PHP_EOL;

				return $accessToken;
			}
		}
	}
	// refresh_token();
?>
