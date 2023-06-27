<?php

include 'push_to_salla.php';

function saveData($data) {
    $productName = $data['egift_line_items'][0]['variant_value'] ?? null;
    $price = ($data['egift_line_items'][0]['price'] ?? null);
    $photo = $data['egift_line_items'][0]['photo'] ?? null;
    $codes = [];
    if (isset($data['egift_line_items'])) {
        foreach ($data['egift_line_items'] as $item) {
            if (isset($item['code']) && !in_array($item['code'], $codes)) {
                $codes[] = $item['code'];
            }
        }
    }
    $description = $data['egift_line_items'][0]['how_to_use']['text'] ?? null;

    $productData = [
        'name' => $productName,
        'price' => $price,
        'status' => "sale",
        'product_type' => "codes",
        'quantity' => 10,
        'images' => [
            [
                'original' => $photo
            ]
        ],
        'codes' => $codes,
        'description' => $description,
        'notify_quantity' => 1
    ];

    $jsonFile = 'products.json';
    $existingData = file_exists($jsonFile) ? json_decode(file_get_contents($jsonFile), true) : [];
    $existingData[$productName] = $productData;
    $newData = json_encode($existingData, JSON_PRETTY_PRINT);
    file_put_contents($jsonFile, $newData);
}

function get_references_ids(){
    $file = fopen("references_ids.txt", "r");
    $success = true; // Flag variable to track the success of the script

    while (($reference = fgets($file)) !== false) {
        $reference = trim($reference);
        $url = "https://channels-api-stage.myresal.com/orders/reconciliation?reference_id=$reference";

        // Set the headers for authorization
        $opts = [
            'http' => [
                'header' => "Authorization: Bearer rsl_chnl_b3fcfc167a6e4c7d9f5bf85c0a64c5f5"
            ]
        ];
        $context = stream_context_create($opts);

        // Make the API call
        $response = file_get_contents($url, false, $context);

        if (!$response) {
            $success = false;
            break; // Exit the loop if an error occurs
        }

        saveData(json_decode($response, true));
    }

    fclose($file);

    if ($success) {
        unlink('references_ids.txt');
        file_put_contents('references_ids.txt', '');
        echo "Products data has been saved to products.json file.". PHP_EOL;

        get_products();
    } else {
        file_put_contents('products.json', '');
        echo "An error occurred during the execution.". PHP_EOL;
    }

}
?>
