const asyncHandler = require('express-async-handler');
const ApiError = require('../utils/apiError');
const ApiFeatures = require('../utils/apiFeatures');
const { cloudinary } = require('../cloudinary');

// const setImageUrl = (doc) => {
//   if (doc.imageCover) {
//     const imageCoverUrl = `${process.env.BASE_URL}/products/${doc.imageCover}`;
//     doc.imageCover = imageCoverUrl;
//   }
//   if (doc.images) {
//     const images = [];
//     doc.images.forEach((image) => {
//       const imageUrl = `${process.env.BASE_URL}/products/${image}`;
//       images.push(imageUrl);
//     });
//     doc.images = images;
//   }
// };

const deleteCloudinaryImage = async (image) => {
  try {
    const cloudinaryUrlParts = image.split('/');
    const public_id = cloudinaryUrlParts.slice(-2).join('/').split('.')[0];
    await cloudinary.uploader.destroy(public_id);        
  } catch (error) {
    console.error('Error deleting image from Cloudinary:', error);
  }
}

exports.deleteOne = (Model) =>
  asyncHandler(async (req, res, next) => {
    const oldDocument = await Model.findById(req.params.id);

    if (oldDocument?.image) {
      await deleteCloudinaryImage(oldDocument.image);
    }

    if (oldDocument?.imageCover) {
      await deleteCloudinaryImage(oldDocument.imageCover);
    }

    if (oldDocument?.images) {
      for(const image of oldDocument.images) {
        await deleteCloudinaryImage(image);
      }
    }

    const document = await Model.findByIdAndDelete(req.params.id);

    if (!document) {
      next(
        new ApiError(`No document found for this id: ${req.params.id}`, 404)
      );
    }
    // To trigger 'remove' event when delete document
    document.remove();
    // 204 no content
    res.status(204).send();
  });

exports.updateOne = (Model) =>
  asyncHandler(async (req, res, next) => {
    const oldDocument = await Model.findById(req.params.id);
    
    const document = await Model.findByIdAndUpdate(req.params.id, req.body, {
      new: true,
    });

    if (!document) {
      return next(
        new ApiError(`No document found for this id: ${req.params.id}`, 404)
      );
    }
  
    // delete old image if exist
    if(oldDocument?.image && document.image != oldDocument.image) {
      await deleteCloudinaryImage(oldDocument.image);
    }

    if (oldDocument?.imageCover && document.imageCover != oldDocument.imageCover) {
      await deleteCloudinaryImage(oldDocument.imageCover);
    }

    if (oldDocument?.images && document.images != oldDocument.images) {
      for(const image of oldDocument.images) {
        await deleteCloudinaryImage(image);
      }
    }

    // To trigger 'save' event when update document
    const doc = await document.save();

    // if (doc.constructor.modelName === 'Product') {
    //   setImageUrl(doc);
    // }
    res.status(200).json({ data: doc });
  });

exports.createOne = (Model) =>
  asyncHandler(async (req, res) => {

    // save image heree...
    console.log(req.body);
    const newDoc = await Model.create(req.body);

    // if (newDoc.constructor.modelName === 'Product') {
    //   setImageUrl(newDoc);
    // }

    res.status(201).json({ data: newDoc });
  });

exports.getOne = (Model, populateOpts) =>
  asyncHandler(async (req, res, next) => {
    const { id } = req.params;
    // Build query
    let query = Model.findById(id);
    if (populateOpts) query = query.populate(populateOpts);

    // Execute query
    const document = await query;

    if (!document) {
      return next(new ApiError(`No document for this id ${id}`, 404));
    }

    // if (document.constructor.modelName === 'Product') {
    //   setImageUrl(document);
    // }

    res.status(200).json({ data: document });
  });

exports.getAll = (Model, modelName = '') =>
  asyncHandler(async (req, res) => {
    let filter = {};
    if (req.filterObject) {
      filter = req.filterObject;
    }

    // Build query
    // const documentsCounts = await Model.countDocuments();
    const apiFeatures = new ApiFeatures(Model.find(filter), req.query)
      .filter()
      .search(modelName)
      .limitFields()
      .sort();
    // .paginate();

    // Apply pagination after filer and search
    const docsCount = await Model.countDocuments(apiFeatures.mongooseQuery);
    apiFeatures.paginate(docsCount);

    // Execute query
    const { mongooseQuery, paginationResult } = apiFeatures;
    const documents = await mongooseQuery;
    console.log(documents);

    // Set Images url
    // if (Model.collection.collectionName === 'products') {
    //   documents.forEach((doc) => setImageUrl(doc));
    // }
    res
      .status(200)
      .json({ results: docsCount, paginationResult, data: documents });
  });

exports.deleteAll = (Model) =>
  asyncHandler(async (req, res, next) => {
    const documents = await Model.find();

    // Loop through the documents and delete their images from Cloudinary
    for (const document of documents) {
      if (document.image){
        await deleteCloudinaryImage(document.image);
      }
    }
    await Model.deleteMany();
    // 204 no content
    res.status(204).send();
  });
