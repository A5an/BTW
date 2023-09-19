let map, infoWindow, autocomplete, marker;

function initMap() {
  map = new google.maps.Map(document.getElementById("map"), {
    center: { lat: -34.397, lng: 150.644 },
    zoom: 15.4,
  });


  autocomplete = new google.maps.places.Autocomplete(
    document.getElementById("places-autocomplete")
  );

  infoWindow = new google.maps.InfoWindow();
  const locationButton = document.createElement("button");


  locationButton.textContent = "Pan to Current Location";
  locationButton.classList.add("custom-map-control-button");
  map.controls[google.maps.ControlPosition.TOP_CENTER].push(locationButton);
  locationButton.addEventListener("click", () => {
    
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const pos = {
            lat: position.coords.latitude,
            lng: position.coords.longitude,
          };

          infoWindow.setPosition(pos);
          infoWindow.setContent("Location found.");
          infoWindow.open(map);
          map.setCenter(pos);
          var marker = new google.maps.Marker({
            position: pos,
            title:"Current Location"
            
            });
            marker.setMap(map);
        },
        () => {
          handleLocationError(true, infoWindow, map.getCenter());
        }
      );
    } else {
      // Browser doesn't support Geolocation
      handleLocationError(false, infoWindow, map.getCenter());
    }

  });
  
  autocomplete.addListener("place_changed", function () {
    const place = autocomplete.getPlace();
    if (!place.geometry) {
      // User entered the name of a place that was not suggested and pressed Enter
      window.alert("Place not found or recognized.");
      return;
    }

    // Clear the previous marker
    if (marker) {
      marker.setMap(null);
    }

    // Handle the selected place, for example:
    const pos = {
      lat: place.geometry.location.lat(),
      lng: place.geometry.location.lng(),
    };

    // Create a new marker at the selected place
    marker = new google.maps.Marker({
      position: pos,
      map: map,
      title: place.name,
    });


    infoWindow.setPosition(pos);
    infoWindow.setContent(place.name);
    infoWindow.open(map);
    map.setCenter(pos);

    // You can also update your form fields with place details if needed
    // For example:
    document.getElementById("latitude").value = pos.lat;
    document.getElementById("longitude").value = pos.lng;
  });
    
}

function handleLocationError(browserHasGeolocation, infoWindow, pos) {
  infoWindow.setPosition(pos);
  infoWindow.setContent(
    browserHasGeolocation
      ? "Error: The Geolocation service failed."
      : "Error: Your browser doesn't support geolocation."
  );
  infoWindow.open(map);
}

window.initMap = initMap;
