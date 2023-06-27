<?php

require_once './vendor/autoload.php';

include 'get_resal_products.php';

use Salla\OAuth2\Client\Provider\Salla;

$provider = new Salla([
    'clientId'     => '248dfd9a-53a4-4a4a-a5e2-7a7990b27e09', // The client ID assigned to you by Salla
    'clientSecret' => '48f1d4767c17b5b6e4277740f6d6b12d', // The client password assigned to you by Salla
    'redirectUri'  => 'https://xbonendo.online/', // the URL for the current page in your service
]);

// Check if it's a webhook request
if ($_SERVER['REQUEST_METHOD'] === 'POST') {

    $webhookPayload = file_get_contents('php://input');

    // Validate the webhook signature
    // You can implement your validation logic here
    $isValidSignature = validateWebhookSignature($_SERVER['HTTP_X_SALLA_SIGNATURE'], $webhookPayload);

    if ($isValidSignature) {
        // Process the webhook payload
        processWebhookPayload($webhookPayload);

        // Respond with a success status
        http_response_code(200);
        echo 'Webhook processed successfully.';
    } else {
        // Respond with an error status
        http_response_code(400);
        echo 'Invalid webhook signature.';
    }

    exit;
}

// Regular flow when not receiving a webhook request
if (empty($_GET['code'])) {
    if (!empty($_GET['error'])) {
        // Handle the case when the user denies authorization
        echo 'Authorization denied.';
        exit;
    }

    // Step 1: Get the authorization URL
    $authUrl = $provider->getAuthorizationUrl([
        'scope' => 'offline_access',
        // Important: If you want to generate the refresh token, set this value as offline_access
    ]);

    // Step 2: Redirect the user to the authorization URL
    header('Location: ' . $authUrl);
    exit;
} else {
    // Step 3: Exchange the authorization code for an access token
    try {
        $token = $provider->getAccessToken('authorization_code', [
            'code' => $_GET['code'],
        ]);

        // Step 4: Process the access token and save it to file
        echo 'Access Token: ' . $token->getToken() . "<br>";
        echo 'Refresh Token: ' . $token->getRefreshToken() . "<br>";
        echo 'Expire Date: ' . $token->getExpires() . "<br>";
        writeTokensToFile($token->getToken(), $token->getRefreshToken(), $token->getExpires());

        get_references_ids();

    } catch (\League\OAuth2\Client\Provider\Exception\IdentityProviderException $e) {
        exit($e->getMessage());
    }
}

function writeTokensToFile($accessToken, $refreshToken, $expires)
{
    $data = [
        'access_token' => $accessToken,
        'refresh_token' => $refreshToken,
        'expires' => $expires
    ];

    $json = json_encode($data);

    $filePath = '/var/www/html/tokens.json';
    file_put_contents($filePath, $json);
}

function validateWebhookSignature($signature, $payload)
{
    // Implement your validation logic here
    // Compare the provided signature with your calculated signature
    // Return true if the signatures match, false otherwise
    return true;
}

function processWebhookPayload($payload)
{
    // Save the webhook payload to a log file
    file_put_contents('/var/www/html/webhook.log', $payload . PHP_EOL, FILE_APPEND);
}
