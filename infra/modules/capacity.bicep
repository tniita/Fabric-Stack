param location string
param capacityName string
param capacityAdmin string
param tags object

resource capacity 'Microsoft.Fabric/capacities@2023-11-01' = {
  name: capacityName
  location: location
  tags: tags
  sku: {
    name: 'F2'
    tier: 'Fabric'
  }
  properties: {
    administration: {
      members: [
        capacityAdmin
      ]
    }
  }
}

output capacityResourceId string = capacity.id