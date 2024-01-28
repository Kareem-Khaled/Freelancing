const { cloudinary } = require('../cloudinary');
const asyncHandler = require('express-async-handler');

const upload = (folder, buffer) => {
  return new Promise((resolve, reject) => {
    const uploadStream = cloudinary.uploader.upload_stream({
      resource_type: 'auto',
      upload_preset: 'ml_default',
      folder,
    }, (error, result) => {
      if (error) {
        console.error('Error uploading to Cloudinary:', error);
        reject(new Error('Cloudinary upload failed'));
      } else {
        resolve(result);
      }
    });
    uploadStream.end(buffer);
  });
};

// upload to cloudinary
const uploadToCloudinary = asyncHandler(async (req, res, next) => {
  const folder = req.baseUrl.split('/').pop();
  try {
    if (req?.file) {
      const { buffer } = req.file;
      const uploadResponse = await upload(folder, buffer);
      req.body.image = uploadResponse.url;
      // console.log('Upload file:', req.body.image);
    }
    if (req?.files?.imageCover) {
      for (const image of req.files.imageCover) {
        const { buffer } = image;
        const uploadResponse = await upload(folder, buffer);
        req.body.imageCover = uploadResponse.url;
      }
      // console.log('Upload imageCover:', req.body.imageCover);
    }
    if (req?.files?.images) {
      req.body.images = [];
      for (const image of req.files.images) {
        const { buffer } = image;
        const uploadResponse = await upload(folder, buffer);
        req.body.images.push(uploadResponse.url);
      }
      // console.log('Upload images:', req.body.images);
    }
    next();
  } catch (error) {
    next(error);
  }
});

module.exports = uploadToCloudinary;
