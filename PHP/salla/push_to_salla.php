<?php
include 'get_tokens.php';

function send_request($curl, $code, $mx_retry = 3, $slp = 1){
    $retryCount = 0;

    while ($retryCount < $mx_retry) {
        $response = curl_exec($curl);

        if ($response === false) {
            $retryCount++;
            sleep($slp);
            continue;
        }

        // Get the response status code
        $statusCode = curl_getinfo($curl, CURLINFO_HTTP_CODE);

        curl_close($curl);

        if ($statusCode == $code) {
            return $response;
        }
        $retryCount++;
    }
    return null;
}

function create_product($data, $codes) {

    $accessToken = get_access_token();
    $headers = [
        'Content-Type: application/json',
        'Accept: application/json',
        'Authorization: Bearer ' . $accessToken,
    ];

    // create product
    $create_url = 'https://api.salla.dev/admin/v2/products';
    $curl = curl_init($create_url);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_POSTFIELDS, $data);
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);
    $response = send_request($curl, 201);

    if(!$response){
        return false;
    }

    // push codes
    $responseData = json_decode($response, true);
    $product_id = $responseData['data']['id'];
    $push_code_url = "https://api.salla.dev/admin/v2/products/$product_id/digital-codes";
    $curl = curl_init($push_code_url);
    curl_setopt($curl, CURLOPT_POST, true);
    curl_setopt($curl, CURLOPT_POSTFIELDS, $codes);
    curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
    curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);

    $response = send_request($curl, 201);

    // delete product if faliles
    if(!$response){
        $delete_url = "https://api.salla.dev/admin/v2/products/$product_id";
        $curl = curl_init($delete_url);
        curl_setopt($curl, CURLOPT_CUSTOMREQUEST, 'DELETE');
        curl_setopt($curl, CURLOPT_HTTPHEADER, $headers);
        curl_setopt($curl, CURLOPT_RETURNTRANSFER, true);

        $response = send_request($curl, 202);

        echo "\nProduct push codes failed" . PHP_EOL;
        return false;
    }

    echo "\nProduct created successfully!" . PHP_EOL;
    return true;
}

function get_products(){
    $file = 'products.json';
    $jsonData = file_get_contents($file);
    $products = json_decode($jsonData, true);

    $success = true; // Flag variable to track the overall success of the script

    if (is_array($products)) {
        foreach ($products as $productName => $product) {
            try {
                $productSuccess = create_product(
                    json_encode($product, true),
                    json_encode(['codes' => $product['codes']])
                );

                if (!$productSuccess) {
                    $success = false; // Set overall success flag to false if any product creation fails
                }
            } catch (Exception $e) {
                $success = false;
                echo 'Error: ' . $e->getMessage() . PHP_EOL;
            }
        }
    }
    else{
        echo "All products were pushed successfully!" . PHP_EOL;
    }

    if ($success) {
        // Clear the JSON file if all code runs without errors
        file_put_contents($file, '');
    }
}
?>
